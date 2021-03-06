import logging
import json

from .cli import cli

import pandas as pd
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold

from services import DataReader, NamingService, DataWriter
from preprocessing import DynamicPreprocessing, InverseDictVectorizer
from classifiers import FVADiseaseClassifier
from noise import SelectNotKBest


@cli.command()
def eliminate_best_k():
    (X, y) = DataReader().read_data('BC')

    for i in range(0, len(X[0].keys()) + 1, 5):

        vect = DictVectorizer(sparse=False)
        selector = SelectNotKBest(k=i)

        pipe = Pipeline([
            # pipe for compare model with eliminating some features
            ('metabolic',
             DynamicPreprocessing(['naming', 'basic-fold-change-scaler'])),
            ('vect', vect),
            ('selector', selector),
            ('inv_vect', InverseDictVectorizer(vect, selector)),
            ('fva', DynamicPreprocessing(['fva']))
        ])

        X_result = pipe.fit_transform(X, y)

        DataWriter('bc_averaging_disease_analysis#k=%s' % i, gz=True) \
            .write_json_dataset(X_result, y)


@cli.command()
def elimination_tabular():
    (X, y) = DataReader().read_data('BC')

    datasets = {'metabolite': DataReader().read_data('BC')}
    scores = list()

    for i in range(0, len(X[0].keys()) + 1, 10):

        vect = DictVectorizer(sparse=False)
        selector = SelectNotKBest(k=i)

        clfs = dict()
        clfs['metabolite'] = Pipeline([
            # pipe for compare model with eliminating some features
            ('metabolic',
             DynamicPreprocessing(['naming', 'metabolic-standard'])),
            ('vect', DictVectorizer(sparse=False)),
            ('selector', SelectNotKBest(k=i)),
            ('pca', PCA(random_state=43)),
            ('clf', LogisticRegression(C=0.01, random_state=43))
        ])

        clfs['pathifier'] = Pipeline([
            # pipe for compare model with eliminating some features
            ('vect', DictVectorizer(sparse=False)),
            ('pca', PCA(random_state=43)),
            ('clf', LogisticRegression(random_state=43))
        ])

        clfs['paradigm'] = Pipeline([
            # pipe for compare model with eliminating some features
            ('vect', DictVectorizer(sparse=False)),
            ('pca', PCA(random_state=43)),
            ('clf', LogisticRegression(C=0.01, random_state=43))
        ])

        clfs['pathway'] = FVADiseaseClassifier()

        try:
            filename = 'bc_averaging_disease_analysis#k=%d' % i
            datasets['pathway'] = DataReader().read_analyze_solution(filename)

            filename = 'bc_pathifier_analysis#k=%d' % i
            datasets['pathifier'] = DataReader().read_analyze_solution(
                filename)

            filename = 'paradigm_results#k=%d' % i
            datasets['paradigm'] = DataReader().read_analyze_solution(
                filename, gz=False)

        except FileNotFoundError:
            print(pd.DataFrame(scores))
            return

        kf = StratifiedKFold(n_splits=10, random_state=43)

        score = {
            name: np.mean(
                cross_val_score(
                    clf,
                    datasets[name][0],
                    datasets[name][1],
                    cv=kf,
                    n_jobs=-1,
                    scoring='f1_micro'))
            for name, clf in clfs.items()
        }
        score['iteration'] = i
        scores.append(score)

        print(pd.DataFrame(scores))
