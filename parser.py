import pandas
import re
import os
import sys
import lxml.etree
import time
import json
import argparse
from collections import defaultdict, Counter
from nltk.tokenize.treebank import TreebankWordDetokenizer
from models import Attribution, Claim, Opinion, Document, Entity, db_session, Predicate
from KafNafParserPy import KafNafParser


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

    def process(self, session, filename):
        print(f"processing: {filename}")
        added_doc = self.write_db([{'name':filename, 'text': self.raw[0]}], session, Document)
        session.commit() # committing for document

        attributions = self.get_attributions()
        claims = self.get_claims()
        opinions = self.get_opinions()
        entities = self.get_entities()
        propositions = self.create_props(self.get_props())

        self.write_db(attributions, session, Attribution, added_doc.id)
        self.write_db(claims, session, Claim, added_doc.id)
        self.write_db(opinions, session, Opinion, added_doc.id)
        self.write_db(entities, session, Entity, added_doc.id)
        self.write_db(propositions, session, Predicate, added_doc.id)
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
                    # print(f"{val}: {untokenized}")
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

    def get_opinion_comment(self, opinion_list):
        opinion_comment = []
        # tokens_mapping = {t.get_id().replace('w', 't'): t.get_sent() for t in self.kaf_parser.get_tokens()}
        for opinion_el in opinion_list:
            comms = {}
            for opinion_part in opinion_el:
                val = opinion_part.xpath('comment()')[0].text
                if opinion_part.tag == "opinion_expression":
                    polarity = opinion_part.xpath('@polarity')
                    tid = opinion_part.xpath('span/target[1]/@id')[0]
                    sent_id = self.tokens_mapping[tid]
                    comms['expression'] = val
                    comms['polarity'] = polarity[0]
                    comms['sent_id'] = sent_id
                if opinion_part.tag == "opinion_target":
                    comms['target'] = val
                if opinion_part.tag == "opinion_holder":
                    comms['holder'] = val
            opinion_comment.append(comms)
        return opinion_comment

    def get_opinions(self):
        all_opinions = self.evaluator('//opinion')
        targets_and_expression = [i.xpath('*[self::opinion_expression | self::opinion_target | self::opinion_holder]')
                                  for i in all_opinions]
        content = self.get_opinion_comment(targets_and_expression)
        return content

    def get_props(self):
        roles = (zip(pred.node.xpath('role/@semRole'), pred.node.xpath('role/comment()'))
                 for pred in self.kaf_parser.get_predicates())
        predicates = ((e.node.xpath('comment()')[0].text,e.node.xpath('child::span/target/@id')) for e in
                      self.kaf_parser.get_predicates())
        return zip(predicates, roles)

    def create_props(self, raw_props):
        # tokens_mapping = {t.get_id().replace('w', 't'): t.get_sent() for t in self.kaf_parser.get_tokens()}
        predicates = []
        for p in raw_props:
            predicate = p[0][0]
            term_id = p[0][1][0]
            sent_id = self.tokens_mapping[term_id]
            roles = p[1]
            themes, texts = zip(*roles)
            role_text = list(map(lambda x: x.text, texts))
            role_dict = json.dumps(dict(zip(themes, role_text)))
            predicates.append({"predicate": predicate, "sent_id": sent_id, "term_id": term_id, "roles": role_dict})
            # print(f"term_id: {term_id}, sent_id:{tokens_mapping[term_id]} predicate:{predicate}: {themes} {role_text}")
        return predicates

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

    def get_ids(self, list_ids):
        needed_ids = []
        for term_el in list_ids:
            id_words = []
            for id in term_el:
                int_val = int(id.split('t')[-1])-1
                id_words.append(int_val)
            needed_ids.append(id_words)
        return needed_ids

    def get_entities(self):
        all_entities = self.evaluator('//entity')
        return [{'value':e.xpath('references/comment()')[0].text, 'type':e.xpath('@type')[0],
                 'sent_id': self.tokens_mapping[e.xpath('references/span/target[1]/@id')[0]]} for e in all_entities]

    def get_people(self):
        return [e.text for e in self.evaluator('entities//entity[@type="PER"]/references/comment()')]

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
        print(f"Time elapsed:{end_time-start_time}")


def combine(doc):
    kaf_tokens = doc.kaf_parser.get_tokens()


if __name__ == "__main__":
    # test1 = '/Users/nadiamanarbelkaid/ATM/conll-allen-nlp/21st-Century-Wire_20170627T181355.conll'
    # test2 = '/Users/nadiamanarbelkaid/ATM/naf-newsreader-nlp/21st-Century-Wire_20170627T181355.naf'
    # doc = Doc(test1, test2)
    # claims = doc.get_claims()

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
    print(f"Total time elapsed parsing all documents {end_total-start_total}")
