from models import Perspective
from sklearn.cluster import KMeans, DBSCAN
from sklearn.feature_extraction import DictVectorizer


perspectives = Perspective.query.filter(Perspective.source_entity.isnot(None)).all()
vectorizer = DictVectorizer(sparse=True)
data = []
for pers in perspectives:
    lowered = {k:v.lower() for k,v in pers.roles_text.items()}
    d = {**lowered}
    d['frame'] = pers.frame
    d['cue'] = pers.cue
    data.append(d)

X = vectorizer.fit_transform(data)

true_k = 6
# model = KMeans(n_clusters=true_k, init='k-means++', max_iter=100, n_init=1)
# model.fit(X)
model = DBSCAN(eps=3, min_samples=2).fit(X)

print("Top terms per cluster:")
order_centroids = model.cluster_centers_.argsort()[:, ::-1]
terms = vectorizer.get_feature_names()
for i in range(true_k):
    print("Cluster %d:" % i),
    for ind in order_centroids[i, :10]:
        print(' %s' % terms[ind]),
    print()

# p = Perspective.query.filter_by(id=1).one()
# y = vectorizer.transform(p.roles_text)
# prediction = model.predict(y)

count = 0
for categorie in range(true_k):
    print(f"Cluster {categorie}".upper())
    for idx, label in enumerate(model.labels_):
        if label == categorie:
            p = perspectives[idx]
            print(count, '\t', p.statement, p.frame.upper(), p.cue.upper())
            count+=1
    print('\n')
    count = 0