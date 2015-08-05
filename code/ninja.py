import copy
from collections import defaultdict
from wide_learning.ninja.ninja_util import (
    Dep, DepGraph, make_ninja_file, outputs
)


CONFIG = {
    'source-data-path': 'source-data/',
    'build-data-path': 'build-data/',
    'glove-versions': ['840B.300d', '42B.300d'],
    'neg-filters': ['jmdict', 'opencyc', 'openmind', 'verbosity', 'wiktionary', 'wordnet'],
    'pos-filters': ['wiktionary'],
    'retrofit-items': ['conceptnet5',
                       'conceptnet5-minus-jmdict',
                       'conceptnet5-minus-opencyc',
                       'conceptnet5-minus-openmind',
                       'conceptnet5-minus-verbosity',
                       'conceptnet5-minus-wiktionary',
                       'conceptnet5-minus-wordnet',
                       'conceptnet5-wiktionary-only',
                       'ppdb-xl-lexical-standardized', 'cnet-ppdb-combined']
}


class GloveVectors:
    """
    A reference to a file containing a matrix of GloVe embeddings.
    """
    def __init__(self, version, *, normalization='none',
                 standardization='raw', retrofit=None,
                 filetype='npy'):
        self.version = version
        self.normalization = normalization
        self.standardization = standardization
        self.retrofit = retrofit
        self.filetype = filetype

    def __repr__(self):
        out = ['glove', self.version, self.normalization, self.standardization]
        if self.retrofit:
            out.append(self.retrofit)
        out.append(self.filetype)
        return CONFIG['build-data-path'] + '.'.join(out)


class GloveLabels:
    """
    A reference to a file containing the labels corresponding to a
    GloveVectors file.
    """
    def __init__(self, version, *, standardization='raw', retrofit=None):
        self.version = version
        self.standardization = standardization
        self.retrofit = retrofit

    def __repr__(self):
        out = ['glove', self.version, self.standardization]
        if self.retrofit:
            out.append(self.retrofit)
        out.append('labels')
        return CONFIG['build-data-path'] + '.'.join(str(x) for x in out)


implicit = {
    'glove_to_vecs': ['wide_learning/builders/build_vecs.py'],
    'filter_vecs': ['wide_learning/builders/filter_vecs.py'],
    'standardize_vecs': ['wide_learning/builders/standardize_vecs.py'],
    'l1_normalize': ['wide_learning/builders/l1norm.py'],
    'l2_normalize': ['wide_learning/builders/l2norm.py'],
    'network_to_assoc': ['wide_learning/builders/build_assoc.py'],
    'add_self_loops': ['wide_learning/builders/self_loops.py'],
    'retrofit': ['wide_learning/builders/retrofit.py'],
    'test': ['wide_learning/evaluation/wordsim.py'],
    'tests_to_latex': ['wide_learning/evaluation/latex_results.py'],
}


def build_wide_learning():
    graph = DepGraph()
    build_glove(graph)

    standardize_ppdb(graph)
    standardize_glove(graph)
    normalize_glove(graph)

    build_assoc(graph)
    filter_conceptnet(graph)
    add_self_loops(graph)
    retrofit(graph)

    test(graph)
    latex_results(graph)

    make_ninja_file('rules.ninja', graph, implicit)


def build_glove(graph):
    for version in CONFIG['glove-versions']:
        input = CONFIG['source-data-path'] + 'glove.%s.txt' % version
        graph['build_glove']['build_glove_labels'][version] = Dep(
            input,
            GloveLabels(version=version),
            'glove_to_labels'
        )
        graph['build_glove']['build_glove_vecs'][version] = Dep(
            input,
            GloveVectors(version=version),
            'glove_to_vecs'
        )


def standardize_glove(graph):
    for version in CONFIG['glove-versions']:
        graph['standardize_glove'][version] = Dep(
            [
                GloveLabels(version=version),
                GloveVectors(version=version)
            ],
            [
                GloveLabels(version=version, standardization='standardized'),
                GloveVectors(version=version, standardization='standardized'),
            ],
            'standardize_vecs'
        )


def standardize_ppdb(graph):
    graph['standardize_ppdb'] = Dep(
        CONFIG['source-data-path'] + 'ppdb-xl-lexical.csv',
        CONFIG['build-data-path'] + 'ppdb-xl-lexical-standardized.csv',
        'standardize_assoc'
    )

    graph['combine_cnet_ppdb'] = Dep(
        [
            CONFIG['source-data-path'] + 'conceptnet5.csv',
            CONFIG['build-data-path'] + 'ppdb-xl-lexical-standardized.csv'
        ],
        CONFIG['build-data-path'] + 'cnet-ppdb-combined.csv',
        'concatenate'
    )


def normalize_glove(graph):
    for version in CONFIG['glove-versions']:
        for norm in ('l1', 'l2'):
            for s13n in ('raw', 'standardized'):
                graph['normalize_glove'][version][norm][s13n] = Dep(
                    GloveVectors(version=version, standardization=s13n),
                    GloveVectors(version=version, normalization=norm, standardization=s13n),
                    '%s_normalize' % norm
                )


def build_assoc(graph):
    version = '840B.300d'
    for network in CONFIG['retrofit-items']:
        path = CONFIG['build-data-path']
        if network == 'conceptnet5':
            path = CONFIG['source-data-path']
        graph['network_to_assoc'][network] = Dep(
            [GloveLabels(version=version, standardization='standardized'), path + network + '.csv'],
            [GloveLabels(version=version, standardization='standardized', retrofit=network), CONFIG['build-data-path'] + network + '.npz'],
            'network_to_assoc'
        )


def regex_for_dataset(dataset):
    if dataset == 'openmind':
        filter_expr = '/d/(globalmind|conceptnet)'
    else:
        filter_expr = '/d/' + dataset
    return filter_expr


def filter_conceptnet(graph):
    for dataset in CONFIG['pos-filters']:
        filter_expr = regex_for_dataset(dataset)
        graph['filter_assoc']['pos'][dataset] = Dep(
            CONFIG['source-data-path'] + 'conceptnet5.csv',
            CONFIG['build-data-path'] + 'conceptnet5-%s-only.csv' % dataset,
            'filter_assoc_pos', params={'filter': filter_expr}
        )

    for dataset in CONFIG['neg-filters']:
        filter_expr = regex_for_dataset(dataset)
        graph['filter_assoc']['neg'][dataset] = Dep(
            CONFIG['source-data-path'] + 'conceptnet5.csv',
            CONFIG['build-data-path'] + 'conceptnet5-minus-%s.csv' % dataset,
            'filter_assoc_neg', params={'filter': filter_expr}
        )



def add_self_loops(graph):
    for network in CONFIG['retrofit-items']:
        graph['add_self_loops'][network] = Dep(
            CONFIG['build-data-path'] + network + '.npz',
            CONFIG['build-data-path'] + network + '.self_loops.npz',
            'add_self_loops'
        )


def retrofit(graph):
    version = '840B.300d'
    for network in CONFIG['retrofit-items']:
        for norm in ['l1', 'l2', 'none']:
            if 'conceptnet5-' in network and norm != 'l1':
                # use only the l1 norm when trying dropping out datasets
                continue
            graph['retrofit'][norm][network] = Dep(
                [
                    GloveVectors(version=version, standardization='standardized', normalization=norm),
                    CONFIG['build-data-path'] + network + '.self_loops.npz'
                ],
                GloveVectors(version=version, standardization='standardized', retrofit=network, normalization=norm),
                'retrofit'
            )


def test(graph):
    vector_files = defaultdict(list)
    for file in outputs(graph):
        if not isinstance(file, GloveVectors):
            continue
        vector_files[file.version, file.standardization, file.retrofit].append(file)

    for (version, standardization, retrofit), files in vector_files.items():
        label = GloveLabels(version=version, standardization=standardization, retrofit=retrofit)
        for file in files:
            out = copy.copy(file)
            out.filetype = 'evaluation'

            graph['test']['test_%s' % file] = Dep(
                [label, file], out, 'test'
            )


def latex_results(graph):
    inputs = []

    graph['latex_results'] = Dep(
        outputs(graph['test']),
        CONFIG['build-data-path'] + 'evaluations.latex',
        'tests_to_latex'
    )


if __name__ == '__main__':
    build_wide_learning()
