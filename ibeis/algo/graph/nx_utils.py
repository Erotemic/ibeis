# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
import numpy as np
import utool as ut
import networkx as nx
import itertools as it
import vtool as vt  # NOQA
from collections import defaultdict
print, rrr, profile = ut.inject2(__name__)


def _dz(a, b):
    a = a.tolist() if isinstance(a, np.ndarray) else list(a)
    b = b.tolist() if isinstance(b, np.ndarray) else list(b)
    return ut.dzip(a, b)


def e_(u, v):
    return (u, v) if u < v else (v, u)


def edges_inside(graph, nodes):
    """
    Finds edges within a set of nodes
    Running time is O(len(nodes) ** 2)

    Args:
        graph (nx.Graph): an undirected graph
        nodes1 (set): a set of nodes
    """
    result = set([])
    upper = nodes.copy()
    graph_adj = graph.adj
    for u in nodes:
        for v in upper.intersection(graph_adj[u]):
            result.add(e_(u, v))
        upper.remove(u)
    return result


def edges_outgoing(graph, nodes1):
    """
    Finds edges between two sets of disjoint nodes.
    Running time is O(len(nodes1) * len(nodes2))

    Args:
        graph (nx.Graph): an undirected graph
        nodes1 (set): set of nodes disjoint from `nodes2`
        nodes2 (set): set of nodes disjoint from `nodes1`.
    """
    nodes1 = set(nodes1)
    return {e_(u, v) for u in nodes1 for v in graph.adj[u] if v not in nodes1}


def edges_cross(graph, nodes1, nodes2):
    """
    Finds edges between two sets of disjoint nodes.
    Running time is O(len(nodes1) * len(nodes2))

    Args:
        graph (nx.Graph): an undirected graph
        nodes1 (set): set of nodes disjoint from `nodes2`
        nodes2 (set): set of nodes disjoint from `nodes1`.
    """
    return {e_(u, v) for u in nodes1
            for v in nodes2.intersection(graph.adj[u])}


def group_name_edges(g, node_to_label):
    ne_to_edges = defaultdict(set)
    for u, v in g.edges():
        name_edge = e_(node_to_label[u], node_to_label[v])
        ne_to_edges[name_edge].add(e_(u, v))
    return ne_to_edges


def ensure_multi_index(index, names):
    import pandas as pd
    if not isinstance(index, (pd.MultiIndex, pd.Index)):
        names = ('aid1', 'aid2')
        if len(index) == 0:
            index = pd.MultiIndex([[], []], [[], []], names=names)
        else:
            index = pd.MultiIndex.from_tuples(index, names=names)
    return index


def demodata_bridge():
    # define 2-connected compoments and bridges
    cc2 = [(1, 2, 4, 3, 1, 4), (8, 9, 10, 8), (11, 12, 13, 11)]
    bridges = [(4, 8), (3, 5), (20, 21), (22, 23, 24)]
    G = nx.Graph(ut.flatten(ut.itertwo(path) for path in cc2 + bridges))
    return G


def demodata_tarjan_bridge():
    # define 2-connected compoments and bridges
    cc2 = [(1, 2, 4, 3, 1, 4), (5, 6, 7, 5), (8, 9, 10, 8),
             (17, 18, 16, 15, 17), (11, 12, 14, 13, 11, 14)]
    bridges = [(4, 8), (3, 5), (3, 17)]
    G = nx.Graph(ut.flatten(ut.itertwo(path) for path in cc2 + bridges))
    return G


def is_edge_connected(G, k):
    """ Determines if G is k-edge-connected """
    if k == 0:
        return True
    elif k == 1:
        return nx.is_connected(G)
    elif k == 2:
        return is_bridge_connected(G)
    else:
        if any(d < k for n, d in G.degree()):
            # quick short circuit for false cases
            return False
        return nx.edge_connectivity(G) >= k


def is_bridge_connected(G):
    return any(find_bridges(G))


def find_bridges(G):
    """
    Returns all bridge edges. A bridge edge is any edge that, if removed, would
    diconnect a compoment in G.

    Notes:
        Bridges can be found using chain decomposition.  An edge e in G is a
        bridge if and only if e is not contained in any chain.

    References:
        https://en.wikipedia.org/wiki/Bridge_(graph_theory)

    Example:
        >>> G = demodata_bridge()
        >>> bridges = find_bridges(G)
        >>> assert bridges == {(3, 5), (4, 8), (20, 21), (22, 23), (23, 24)}
        >>> import plottool as pt
        >>> pt.qtensure()
        >>> pt.show_nx(G)
    """
    chain_edges = set(it.starmap(e_, it.chain(*nx.chain_decomposition(G))))
    bridges = set(it.starmap(e_, G.edges())) - chain_edges
    return bridges


def bridge_connected_compoments(G):
    """
    Example:
        >>> G = demodata_bridge()
        >>> bridge_ccs = bridge_connected_compoments(G)
        >>> assert bridge_ccs == [
        >>>     {1, 2, 3, 4}, {5}, {8, 9, 10}, {11, 12, 13}, {20},
        >>>     {21}, {22}, {23}, {24}
        >>> ]
    """
    bridges = find_bridges(G)
    H = G.copy()
    H.remove_edges_from(bridges)
    return list(nx.connected_components(H))


def edge_connected_augmentation(G, k, candidates=None, hack=False):
    r"""
    CommandLine:
        python -m ibeis.algo.graph.nx_utils edge_connected_augmentation

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.graph.nx_utils import *  # NOQA
        >>> G = nx.Graph()
        >>> G.add_nodes_from([1, 2, 3, 4, 5, 6])
        >>> k = 4
        >>> aug_edges = edge_connected_augmentation(G, k)
        >>> G.add_edges_from(aug_edges)
        >>> print(nx.edge_connectivity(G))
        >>> import plottool as pt
        >>> pt.qtensure()
        >>> pt.show_nx(G)
        >>> ut.show_if_requested()

    Example:
        >>> from ibeis.algo.graph.nx_utils import *  # NOQA
        >>> G = nx.Graph()
        >>> G.add_nodes_from([
        >>>     1105, 1106, 2547, 2548, 1119, 1190, 3095, 2712, 2714, 1531, 2779])
        >>> G.add_edges_from([(2547, 1531)])
        >>> impossible = {(1190, 2547), (2547, 2779)}
        >>> candidates = list(set(nx.complement(G).edges()) - impossible)
        >>> aug_edges = edge_connected_augmentation(G, k=1)
        >>> aug_edges = edge_connected_augmentation(G, 1, candidates)
    """
    if is_edge_connected(G, k):
        aug_edges = []
    elif k == 1 and candidates is None and not hack:
        C = collapse(G, nx.connected_components(G))
        roots = [min(cc, key=C.degree) for cc in nx.connected_components(C)]
        forest_aug = list(zip(roots, roots[1:]))
        C.add_edges_from(forest_aug)
        # map these edges back to edges in the original graph
        inverse = {v: k for k, v in C.graph['mapping'].items()}
        # inverse = ut.invert_dict(C.graph['mapping'], unique_vals=False)
        aug_edges = [(inverse[u], inverse[v]) for u, v in forest_aug]
    elif k == 1 and candidates is not None and not hack:
        # Construct a tree with the candidates and original edges
        # The original edges costs 0, and each candidate costs 1
        H = G.copy()
        orig_edges = list(G.edges())
        nx.set_edge_attributes(H, 'weight', ut.dzip(orig_edges, [0]))
        H.add_edges_from(candidates)
        nx.set_edge_attributes(H, 'weight', ut.dzip(candidates, [1]))
        T = nx.minimum_spanning_tree(H)
        if not nx.is_connected(T):
            print('could not connect T')
        T.remove_edges_from(orig_edges)
        aug_edges = list(it.starmap(e_, T.edges()))
    elif k == 2 and candidates is None and not hack:
        aug_edges = bridge_connected_augmentation(G)
    else:
        # Because I have not implemented a better algorithm yet:
        # randomly add edges until we satisfy the criteria
        import random
        rng = random.Random(0)
        # very hacky and not minimal
        H = G.copy()
        aug_edges = []
        if candidates is None:
            candidates = list(nx.complement(G).edges())
        else:
            candidates = list(candidates)
        while len(candidates):
            edge = rng.choice(candidates)
            candidates.remove(edge)
            aug_edges.append(edge)
            H.add_edge(*edge)
            if is_edge_connected(G, k):
                break
        # Greedy attempt to reduce the size
        for edge in list(aug_edges):
            if min(H.degree(edge), key=lambda t: t[1])[1] <= k:
                continue
            H.remove_edge(*edge)
            aug_edges.remove(edge)
            conn = nx.edge_connectivity(H)
            if conn < k:
                # If no longer feasible undo
                H.add_edge(*edge)
                aug_edges.append(edge)
    return aug_edges


def bridge_connected_augmentation(G):
    """
    References:
        http://www.openu.ac.il/home/nutov/Gilad-Thesis.pdf
        http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.30.2256&rep=rep1&type=pdf
        http://search.proquest.com/docview/918506142?accountid=28525
        http://epubs.siam.org/doi/abs/10.1137/0205044
        https://en.wikipedia.org/wiki/Bridge_(graph_theory)#Bridge-Finding_with_Chain_Decompositions

    Notes:
        bridge-connected:
            G is bridge-connected if it is connected and contains no bridges.

        arborescence:
            An arborescence is a DAG with only one source vertex.
            IE.  The root (source) has no entering edge, and all other
            verticies have at least one entering edge.
            An arborescence is thus the directed-graph form of a rooted tree.
            Is a directed graph in which, for a vertex u called the root and
            any other vertex v, there is exactly one directed path from u to v.

        pendant / leaf:
            A vertex of a graph is said to be (pendant / leaf) if its
            neighborhood contains exactly one vertex.

    Example:
        >>> from ibeis.algo.graph.nx_utils import *
        >>> import networkx as nx
        >>> G = demodata_tarjan_bridge()
        >>> bridge_edges = edge_connectivity_augmentation(G)
        >>> import plottool as pt
        >>> pt.qtensure()
        >>> pt.nx_agraph_layout(G, inplace=True, prog='neato')
        >>> nx.set_node_attributes(G, 'pin', 'true')
        >>> G2 = G.copy()
        >>> G2.add_edges_from(bridge_edges)
        >>> pt.nx_agraph_layout(G2, inplace=True, prog='neato')
        >>> pt.show_nx(G, fnum=1, pnum=(1, 2, 1), layout='custom')
        >>> pt.show_nx(G2, fnum=1, pnum=(1, 2, 2), layout='custom')

    Example:
        >>> from ibeis.algo.graph.nx_utils import *
        >>> import networkx as nx
        >>> G = nx.Graph()
        >>> G.add_nodes_from([1, 2, 3, 4])
        >>> bridge_edges = edge_connectivity_augmentation(G)
        >>> import plottool as pt
        >>> pt.qtensure()
        >>> pt.nx_agraph_layout(G, inplace=True, prog='neato')
        >>> nx.set_node_attributes(G, 'pin', 'true')
        >>> G2 = G.copy()
        >>> G2.add_edges_from(bridge_edges)
        >>> pt.nx_agraph_layout(G2, inplace=True, prog='neato')
        >>> pt.show_nx(G, fnum=1, pnum=(1, 2, 1), layout='custom')
        >>> pt.show_nx(G2, fnum=1, pnum=(1, 2, 2), layout='custom')
    """
    if G.number_of_nodes() < 3:
        raise ValueError('impossible to bridge connect less than 3 verticies')
    # find the bridge-connected components of G
    bridge_ccs = bridge_connected_compoments(G)
    # condense G into an forest C
    C = collapse(G, bridge_ccs)
    # Connect each tree in the forest to construct an arborescence
    # (I think) these must use nodes with minimum degree
    roots = [min(cc, key=C.degree) for cc in nx.connected_components(C)]
    forest_bridges = list(zip(roots, roots[1:]))
    C.add_edges_from(forest_bridges)
    # order the leaves of C by preorder
    leafs = [n for n in nx.dfs_preorder_nodes(C) if C.degree(n) == 1]
    # construct edges to bridge connect the tree
    tree_bridges = list(zip(leafs, leafs[1:]))
    # collect the edges used to augment the original forest
    aug_tree_edges = tree_bridges + forest_bridges
    # map these edges back to edges in the original graph
    inverse = {v: k for k, v in C.graph['mapping'].items()}
    bridge_edges = [(inverse[u], inverse[v]) for u, v in aug_tree_edges]
    return bridge_edges


def collapse(G, grouped_nodes):
    """Collapses each group of nodes into a single node.

    TODO: submit as PR

    This is similar to condensation, but works on undirected graphs.

    Parameters
    ----------
    G : NetworkX Graph
       A directed graph.

    grouped_nodes:  list or generator
       Grouping of nodes to collapse. The grouping must be disjoint.
       If grouped_nodes are strongly_connected_components then this is
       equivalent to condensation.

    Returns
    -------
    C : NetworkX Graph
       The collapsed graph C of G with respect to the node grouping.  The node
       labels are integers corresponding to the index of the component in the
       list of strongly connected components of G.  C has a graph attribute
       named 'mapping' with a dictionary mapping the original nodes to the
       nodes in C to which they belong.  Each node in C also has a node
       attribute 'members' with the set of original nodes in G that form the
       group that the node in C represents.

    Examples
    --------
    Collapses a graph using disjoint groups, but not necesarilly connected
    >>> G = nx.Graph([(1, 0), (2, 3), (3, 1), (3, 4), (4, 5), (5, 6), (5, 7)])
    >>> G.add_node('A')
    >>> grouped_nodes = [{0, 1, 2, 3}, {5, 6, 7}]
    >>> C = collapse(G, grouped_nodes)
    >>> assert nx.get_node_attributes(C, 'members') == {
    >>>     0: {0, 1, 2, 3}, 1: {5, 6, 7}, 2: {4}, 3: {'A'}
    >>> }
    """
    mapping = {}
    members = {}
    C = G.__class__()
    i = 0  # required if G is empty
    remaining = set(G.nodes())
    for i, group in enumerate(grouped_nodes):
        group = set(group)
        assert remaining.issuperset(group), (
            'grouped nodes must exist in G and be disjoint')
        remaining.difference_update(group)
        members[i] = group
        mapping.update((n, i) for n in group)
    # remaining nodes are in their own group
    for i, node in enumerate(remaining, start=i + 1):
        group = set([node])
        members[i] = group
        mapping.update((n, i) for n in group)
    number_of_groups = i + 1
    C.add_nodes_from(range(number_of_groups))
    C.add_edges_from((mapping[u], mapping[v]) for u, v in G.edges()
                     if mapping[u] != mapping[v])
    # Add a list of members (ie original nodes) to each node (ie scc) in C.
    nx.set_node_attributes(C, 'members', members)
    # Add mapping dict as graph attribute
    C.graph['mapping'] = mapping
    return C


def edge_connected_components(G, k):
    """
    We can find all k-edge-connected-components

    For k in {1, 2} the algorithm runs in O(n)
    For other k the algorithm runs in O(n^5)

    References:
        wang_simple_2015
        http://journals.plos.org/plosone/article?id=10.1371/journal.pone.0136264

    Example:
        >>> from ibeis.algo.graph.nx_utils import *
        >>> import networkx as nx
        >>> G = demodata_tarjan_bridge()
        >>> print(list(edge_connected_components(G, k=1)))
        >>> print(list(edge_connected_components(G, k=2)))
        >>> print(list(edge_connected_components(G, k=3)))
        >>> print(list(edge_connected_components(G, k=4)))
    """
    if k == 1:
        return nx.connected_components(G)
    elif k == 2:
        return bridge_connected_compoments(G)
    else:
        # FIXME: there is an efficient algorithm for k == 3
        G = G.copy()
        nx.set_edge_attributes(G, 'capacity', ut.dzip(G.edges(), [1]))
        A = aux_graph(G)
        return query_aux_graph(A, k)


def aux_graph(G, source=None, avail=None, A=None):
    """
    Max-flow O(F) = O(n^3)
    Auxiliary Graph = O(Fn) = O(n^4)

    on receiving a graph G = (V, E), a vertex s (the source) and a set of
    available vertices N (vertices that can be chosen as the sink), the
    algorithm randomly picks a vertex t 2 N − {s}, and runs the max-flow
    algorithm to determine the max-flow from s to t.

    We also set (S, T) to the corresponding min-cut (
        for the case where G is undirected, (S, T) is already the desired
        min-cut).

    Then, an edge (s, t) with weight x is added to the auxiliary graph A.

    The procedure then calls itself recursively, first with S as the set of
    available vertices and s as the source, and then with T as the set of
    available vertices and t as the source.

    The recursive calls terminate when S or T is reduced to a single vertex.

    CommandLine:
        python -m ibeis.algo.graph.nx_utils aux_graph --show

    Example:
        >>> # Example
        >>> from ibeis.algo.graph.nx_utils import *
        >>> a, b, c, d, e, f, g = ut.chr_range(7)
        >>> di_paths = [
        >>>     (a, d, b, f, c),
        >>>     (a, e, b),
        >>>     (a, e, b, c, g, b, a),
        >>>     (c, b),
        >>>     (f, g, f),
        >>> ]
        >>> G = nx.DiGraph(ut.flatten(ut.itertwo(path) for path in di_paths))
        >>> nx.set_edge_attributes(G, 'capacity', ut.dzip(G.edges(), [1]))
        >>> A = aux_graph(G, source=a)
        >>> import plottool as pt
        >>> attrs = pt.nx_agraph_layout(G, inplace=True, prog='neato')[1]
        >>> nx.set_node_attributes(G, 'pin', 'true')
        >>> nx.set_edge_attributes(A, 'label', nx.get_edge_attributes(A, 'capacity'))
        >>> for key in list(attrs['node'].keys()) + ['pin']:
        >>>     nx.set_node_attributes(A, key, nx.get_node_attributes(G, key))
        >>> pt.nx_agraph_layout(A, inplace=True, prog='neato')
        >>> pt.show_nx(G, fnum=1, pnum=(1, 2, 1), layout='custom', arrow_width=1)
        >>> pt.show_nx(A, fnum=1, pnum=(1, 2, 2), layout='custom', arrow_width=1)
        >>> ut.show_if_requested()

    G = G.copy()
    nx.set_edge_attributes(G, 'capacity', ut.dzip(G.edges(), [1]))
    A = aux_graph(G)
    G.node
    A.node
    A.edge

    """
    if source is None:
        source = next(G.nodes())
    if avail is None:
        avail = set(G.nodes())
    if A is None:
        A = G.__class__()
        # A.add_node(source)
    if {source} == avail:
        return A
    # pick an arbitrary vertex as the sink
    sink = next(iter(avail - {source}))

    x, (S, T) = nx.minimum_cut(G, source, sink)
    if G.is_directed():
        x_, (T_, S_) = nx.minimum_cut(G, source, sink)
        if x_ < x:
            x, S, T = x_, T_, S_

    # add edge with weight of cut to the aug graph
    A.add_edge(source, sink, capacity=x)

    # if len(S) == 1 or len(T) == 1:
    #     return A

    aux_graph(G, source, avail.intersection(S), A=A)
    aux_graph(G, sink, avail.intersection(T), A=A)
    return A


def query_aux_graph(A, k):
    """ Query of the aux graph can be done via DFS in O(n) """
    # After the auxiliary graph A is constructed, for each query k, the
    # k-edge-connected components can be easily determined as follows:
    # traverse A and delete all edges with weights less than k.
    # Then, each connected component in the resulting graph represents a
    # k-edge-connected component in G.
    weights = nx.get_edge_attributes(A, 'capacity')
    relevant_edges = {e for e, w in weights.items() if w >= k}
    relevant_graph = nx.Graph(list(relevant_edges))
    relevant_graph.add_nodes_from(A.nodes())
    return nx.connected_components(relevant_graph)


if __name__ == '__main__':
    r"""
    CommandLine:
        python -m ibeis.algo.graph.nx_utils
        python -m ibeis.algo.graph.nx_utils --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
