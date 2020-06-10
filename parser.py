import pandas
import re
import os
import lxml.etree
import time
import json
import argparse
import sys
import operator
import csv
from collections import defaultdict, OrderedDict
from models import Attribution, Claim, Document, Entity, db_session
from models import Perspective as PerspectiveModel
from KafNafParserPy import KafNafParser
from KafNafParserPy import Cpredicate
from KafNafParserPy import Copinion
from nltk.tokenize.treebank import TreebankWordDetokenizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyser = SentimentIntensityAnalyzer()
path_to_sip_file = 'sip-frames.txt'
path_to_metadata = 'metadata.tsv'
with open(path_to_sip_file) as fp:
    sip_frames = fp.read().splitlines()

with open(path_to_metadata) as fp:
    reader = csv.reader(fp, delimiter='\t')
    #skip line for header
    next(reader)
    doc_metadata = {line[0]: line[1:] for line in reader}

DETOKENIZER = TreebankWordDetokenizer()


class Perspective:
    def __init__(self, predicate_info, opinion_info, source_article_id, source_entity=None, target_entity=None):
        self.predicate_info = predicate_info
        self.opinion_info = opinion_info
        self.source_article = source_article_id
        self.all_terms = self.predicate_info['all_terms']
        self.all_tokens = self.predicate_info['all_tokens']
        self.term_word_mapping = self.gen_term_word_mapping(self.all_tokens)
        self.source_entity = source_entity
        self.target_entity = target_entity
        self.cue = predicate_info['predicate']
        self.sentiment = self.get_sentiment()
        self.frame = predicate_info['frame']

    def return_statement(self):
        return DETOKENIZER.detokenize(
            [self.all_tokens[token].get_text() for token in sorted(self.predicate_info['all_tokens'],
                                                                   key=lambda x: int(x[1:]))])

    def return_role_text(self):
        return {role: self.get_tokens(self.predicate_info['roles'].get(role)) for role in self.predicate_info['roles']}

    def gen_term_word_mapping(self, token_maping):
        return {k.replace('w', 't'): v.get_text() for k, v in token_maping.items()}

    def get_tokens(self, list_term_ids):
        return ' '.join([self.term_word_mapping[item] for item in list_term_ids])

    def return_opinions(self):
        opinions = []
        for opinion in self.opinion_info:
            expression = DETOKENIZER.detokenize(
                [self.term_word_mapping.get(term_id) for term_id in opinion['expression']])
            target = DETOKENIZER.detokenize([self.term_word_mapping.get(term_id) for term_id in opinion['target']])
            expression_span = opinion['expression']
            target_span = opinion['target']
            polarity = opinion['opinion'].get_expression().get_polarity()
            opinions.append({'expression': expression,
                             'target': target,
                             'polarity': polarity,
                             'expression_span': expression_span,
                             'target_span': target_span,
                             'frame': self.frame})
        return opinions

    def get_sentiment(self):
        sent = analyser.polarity_scores(self.return_statement())
        del sent['compound']
        return max(sent.items(), key=operator.itemgetter(1))[0]

    def store_perspective(self):
        session = db_session()
        data = {'statement': self.return_statement(),
                'statement_span': OrderedDict((term, self.term_word_mapping[term]) for term in self.all_terms),
                'cue': self.get_tokens(self.cue),
                'opinion_info': self.return_opinions(),
                'roles_span': self.predicate_info['roles'],
                'roles_text': self.return_role_text(),
                'order': self.predicate_info['order'].text,
                'term_to_word': self.term_word_mapping,
                'source_entity': self.source_entity,
                'target_entity': self.target_entity,
                'doc_id': self.source_article,
                'sentiment': self.sentiment,
                'frame': self.frame
                }
        session.add(PerspectiveModel(**data))
        session.commit()

    def __repr__(self):
        # return f"<Predicate: {self.predicate_info}>"
        return f"<{self.return_statement()}>"


class Doc:
    def __init__(self, file_path_conll, file_path_kaf):
        self.conll_path = file_path_conll
        self.kaf_path = file_path_kaf
        self.df = pandas.read_csv(self.conll_path, engine='python', error_bad_lines=False, delimiter='\t')
        self.df = self.df.fillna('-')
        self.kaf = lxml.etree.ElementTree(file=self.kaf_path)
        self.kaf_parser = KafNafParser(self.kaf_path)
        self.evaluator = lxml.etree.XPathEvaluator(self.kaf)
        self.df.index += 1
        self.raw = self.evaluator('raw/text()')
        self.tokens_mapping = {t.get_id().replace('w', 't'): t.get_sent() for t in self.kaf_parser.get_tokens()}
        self.opinion_term_mapping = {
            opinion.get_id(): [element.attrib['id'] for element in opinion.node.iterdescendants()
                               if element.tag == 'target'] for opinion in self.kaf_parser.get_opinions()}
        self.opinion_idx = {opinion.get_id(): opinion.get_node() for opinion in self.kaf_parser.get_opinions()}
        self.entities = self.get_entities()
        self.entities_span = [e['span'] for e in self.entities]

    def process(self, session, filename):
        nfilename = filename.split('.')[0]
        print(f"processing: {filename}")
        metadata = doc_metadata[nfilename]
        added_doc = self.write_db([{'name': nfilename,
                                    'text': self.raw[0],
                                    'url': metadata[0],
                                    'publisher': metadata[-3],
                                    'author': metadata[-2]}],
                                  session, Document)

        session.commit()  # committing for document
        events = self.get_props()
        perspectives = self.generate_perspectives(events, added_doc)
        attributions = self.get_attributions()
        claims = self.get_claims()
        self.write_db(attributions, session, Attribution, added_doc.id)
        self.write_db(claims, session, Claim, added_doc.id)
        self.write_db(self.entities, session, Entity, added_doc.id)
        session.commit()

    def get_attributions(self):
        beginning_attr_content = self.df[self.df['attr_content'].str.contains('B-content')]['attr_content'].values
        splitted_content = [re.split(':|_|#', val) for val in beginning_attr_content]
        attr_identifiers = Doc.convert_attr(splitted_content)
        attributions = []
        try:
            for vals in attr_identifiers.values():
                extracted = {}
                for item in vals.items():
                    col, val = item
                    df_rows = self.df[self.df[col].str.contains(val)]
                    tokens = df_rows.groupby('sent_id')['word'].apply(list)
                    tokens_id = df_rows.groupby('sent_id')['token_id'].apply(list)
                    untokenized = TreebankWordDetokenizer().detokenize(tokens.values[0])
                    sent_id = tokens.index[0]
                    extracted[val.split('-')[0]] = untokenized
                    extracted['sent_id'] = int(sent_id)

                attributions.append(extracted)
        except IndexError:
            print("couldn't find claims")
        return attributions

    def get_claims(self):
        df = self.df[self.df['claim'].str.contains('claim')]
        grouped = df.groupby('sent_id')['word'].apply(list)
        grouped_token_id = df.groupby('sent_id')['token_id'].apply(list)
        sentences = []
        for sent_id, sent in grouped.items():
            sentences.append({'value': TreebankWordDetokenizer().detokenize(sent), 'sent_id': sent_id,
                              'token_ids': json.dumps(grouped_token_id[sent_id])})
        return sentences

    def get_props(self):
        x_statement = 'externalReferences[1]/externalRef[@resource="FrameNet"]/@reference'
        return ((pred.node.values()[0], pred.node.xpath(x_statement)[0]) for pred in self.kaf_parser.get_predicates() if
                set(pred.node.xpath(x_statement)).intersection(sip_frames))

    def get_opinion_data(self, opinion_id):
        extracted_opinion = {}
        opinion_element = self.opinion_idx[opinion_id]
        opinion = Copinion(opinion_element)
        target = opinion.get_target()
        holder = opinion.get_holder()
        if not target:
            return None
        extracted_opinion['target'] = target.get_span().get_span_ids()
        if holder:
            extracted_opinion['holder'] = holder.get_span().get_span_ids()
        extracted_opinion['expression'] = opinion.get_expression().get_span().get_span_ids()
        extracted_opinion['opinion'] = opinion
        return extracted_opinion

    def get_srl_data(self, pred_id):
        ext_pred = {}
        predicate_element = self.kaf_parser.srl_layer.idx[pred_id]
        kaf_pred = Cpredicate(predicate_element)
        ext_pred['predicate'] = kaf_pred.get_span().get_span_ids()
        ext_pred['roles'] = OrderedDict(
            (role.get_semRole(), role.get_span().get_span_ids()) for role in kaf_pred.get_roles())
        ext_pred['order'] = predicate_element.getprevious()
        ext_pred['all_term_ids'] = [element.attrib['id'] for element in predicate_element.iterdescendants() if
                                    element.tag == 'target']
        ext_pred['all_terms'] = {term_id: self.kaf_parser.get_term(term_id) for term_id in ext_pred['all_term_ids']}
        ext_pred['all_tokens'] = {}
        for token_id in ext_pred['all_term_ids']:
            token_id = token_id.replace('t', 'w')
            ext_pred['all_tokens'][token_id] = self.kaf_parser.get_token(token_id)

        return ext_pred

    def generate_perspectives(self, events, added_doc):
        perspectives = []
        for event_id in events:
            opinion_data = []
            pred = self.get_srl_data(event_id[0])
            pred['frame'] = event_id[1]
            for opinion_id, term_ids in self.opinion_term_mapping.items():
                if set(term_ids).issubset(set(pred['all_term_ids'])):
                    extracted_opinion = self.get_opinion_data(opinion_id)
                    if extracted_opinion:
                        opinion_data.append(extracted_opinion)
            p = Perspective(pred, opinion_data, added_doc.id)
            perspectives.append(p)
            a0 = pred['roles'].get('A0')
            a1 = pred['roles'].get('A1')
            if a1:
                if a0 in self.entities_span:
                    p.source_entity = p.get_tokens(a0)
                if a1 in self.entities_span:
                    p.target_entity = p.get_tokens(a1)
            p.store_perspective()
        return perspectives

    @staticmethod
    def convert_attr(attr_list):
        attrs = {}
        for i, el in enumerate(attr_list):
            per_content = {}
            for part in el:
                if part[0].isdigit():
                    s = part.split('-')
                    formatted = s[1] + '-' + s[0]
                    formatted = formatted.lower()
                    if 'cue' in formatted:
                        per_content['attr_cue'] = formatted
                    elif 'source' in formatted:
                        per_content['attr_source'] = formatted
            per_content['attr_content'] = el[0][2:]
            attrs[i] = per_content
        return attrs

    def get_entities(self):
        all_entities = self.kaf_parser.get_entities()
        return [{'value': e.node.xpath('references/comment()')[0].text,
                 'type': e.node.xpath('@type')[0],
                 'span': list(e.get_references())[0].get_span().get_span_ids(),
                 'sent_id': self.tokens_mapping[e.node.xpath('references/span/target[1]/@id')[0]]} for e in
                all_entities]

    def write_db(self, content_list, session, db_model, document_id=None):
        for e in content_list:
            if document_id:
                obj = db_model(doc_id=document_id, **e)
            else:
                obj = db_model(**e)
                session.add(obj)
                return obj
            session.add(obj)


def start(path_dict):
    session = db_session()
    for fn in path_dict:
        paths = path_dict[fn]
        first_file = paths.pop()
        if paths:
            if first_file.split('.')[1] == 'kaf':
                doc = Doc(file_path_conll=first_file, file_path_kaf=paths[0])
            else:
                doc = Doc(file_path_conll=paths[0], file_path_kaf=first_file)
        start_time = time.time()
        doc.process(session, fn)
        end_time = time.time()
        print(f"Time elapsed:{end_time - start_time}")


if __name__ == "__main__":
    # test1 = '/Users/nadiamanarbelkaid/ATM/conll-mate-nlp/Backyard-Secret-Exposed_20161021T055227.conll'
    # test2 = '/Users/nadiamanarbelkaid/ATM/naf-newsreader-nlp/Backyard-Secret-Exposed_20161021T055227.naf'
    # doc = Doc(test1, test2)
    # ses = db_session()
    # doc.process(ses, test2)

    parser = argparse.ArgumentParser()
    parser.add_argument('conll_fp')
    parser.add_argument('kaf_fp')
    args = parser.parse_args()

    dir1 = args.conll_fp
    dir2 = args.kaf_fp
    dir_list = [dir1, dir2]

    file_paths = defaultdict(list)
    for d_path in dir_list:
        for f in os.listdir(d_path):
            fp = os.path.join(d_path, f)
            fn = os.path.basename(os.path.splitext(fp)[0])
            file_paths[fn].append(fp)

    notok = filter(lambda x: len(x) < 1, file_paths.values())

    if list(notok):
        print('something went wrong with the directories')
        sys.exit(1)
    start_total = time.time()
    start(file_paths)
    end_total = time.time()
    print(f"Total time elapsed parsing all documents {end_total - start_total}")
