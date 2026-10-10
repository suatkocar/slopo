from slopo.result.models import Cluster, SimilarPair


def cluster_pairs(pairs: list[SimilarPair]) -> list[set[int]]:
    # Groups unit IDs into clusters by transitive similarity: if A~B and B~C,
    # all three end up in the same set. Each set in the result is one cluster,
    # ordered by the last pair that joined it. A union-find keeps this linear in
    # the number of pairs. Scanning every group for every pair, and every pair
    # for every group afterwards, grew with their product: analyzing 34k units,
    # most of them exact copies, took 87 s that way and 7.7 s with this and
    # pairs_by_cluster, for an identical report (M3 Max, 2026-10-10).
    parent: dict[int, int] = {}
    size: dict[int, int] = {}
    last_pair: dict[int, int] = {}

    def find(unit: int) -> int:
        root = unit
        while parent[root] != root:
            root = parent[root]
        while parent[unit] != root:
            parent[unit], unit = root, parent[unit]
        return root

    for index, pair in enumerate(pairs):
        for unit in (pair.unit_id_a, pair.unit_id_b):
            if unit not in parent:
                parent[unit] = unit
                size[unit] = 1
        a, b = find(pair.unit_id_a), find(pair.unit_id_b)
        if a != b:
            if size[a] < size[b]:
                a, b = b, a
            parent[b] = a
            size[a] += size[b]
        last_pair[a] = index

    groups: dict[int, set[int]] = {}
    for unit in parent:
        groups.setdefault(find(unit), set()).add(unit)
    return [groups[root] for root in sorted(groups, key=lambda root: last_pair[root])]


def pairs_by_cluster(
    clusters: list[Cluster], pairs: list[SimilarPair]
) -> list[list[SimilarPair]]:
    # The pairs whose two units both belong to each cluster, in their order,
    # found in one pass over the pairs instead of one pass per cluster.
    clusters_of: dict[int, list[int]] = {}
    for number, cluster in enumerate(clusters):
        for uid in cluster.unit_ids:
            clusters_of.setdefault(uid, []).append(number)
    found: list[list[SimilarPair]] = [[] for _ in clusters]
    for p in pairs:
        both = clusters_of.get(p.unit_id_b, [])
        for number in clusters_of.get(p.unit_id_a, []):
            if number in both:
                found[number].append(p)
    return found


def sort_cluster(unit_ids: set[int], pairs: list[SimilarPair]) -> list[int]:
    # Orders units so adjacent pairs are as similar as possible. Starts with the
    # highest-similarity pair, then greedily appends the unit most similar to the
    # last one added. lookup is a symmetric dict {(a, b): similarity} for O(1) access.
    if len(unit_ids) <= 2:
        if len(unit_ids) == 2:
            a, b = sorted(unit_ids)
            return (
                [a, b]
                if _similarity(a, b, pairs) >= _similarity(b, a, pairs)
                else [b, a]
            )
        return list(unit_ids)

    lookup: dict[tuple[int, int], float] = {}
    for p in pairs:
        if p.unit_id_a in unit_ids and p.unit_id_b in unit_ids:
            lookup[(p.unit_id_a, p.unit_id_b)] = p.similarity
            lookup[(p.unit_id_b, p.unit_id_a)] = p.similarity

    def sim(a: int, b: int) -> float:
        return lookup.get((a, b), 0.0)

    sorted_ids = sorted(unit_ids)
    best_pair = max(
        ((a, b) for a in sorted_ids for b in sorted_ids if a != b),
        key=lambda ab: sim(ab[0], ab[1]),
    )

    path = [best_pair[0], best_pair[1]]
    remaining = unit_ids - {best_pair[0], best_pair[1]}

    while remaining:
        last = path[-1]
        next_unit = max(remaining, key=lambda u: sim(last, u))
        path.append(next_unit)
        remaining.remove(next_unit)

    return path


def reorder_clusters(
    clusters: list[Cluster], reranked_pairs: list[SimilarPair]
) -> list[Cluster]:
    result: list[Cluster] = []
    found = pairs_by_cluster(clusters, reranked_pairs)
    for cluster, in_cluster in zip(clusters, found):
        members = set(cluster.unit_ids)
        ordered = sort_cluster(members, in_cluster)
        sims = [p.similarity for p in in_cluster]
        min_sim = min(sims)
        max_sim = max(sims)
        result.append(
            Cluster(unit_ids=ordered, min_similarity=min_sim, max_similarity=max_sim)
        )
    result.sort(key=lambda c: c.max_similarity, reverse=True)
    return result


def filter_clusters(clusters: list[Cluster], threshold: float) -> list[Cluster]:
    return [c for c in clusters if c.max_similarity >= threshold]


def build_clusters(pairs: list[SimilarPair]) -> list[Cluster]:
    raw_groups = cluster_pairs(pairs)
    clusters: list[Cluster] = []

    # Every pair joins its two units, so it belongs to exactly one group.
    group_of = {uid: number for number, group in enumerate(raw_groups) for uid in group}
    group_pairs: list[list[SimilarPair]] = [[] for _ in raw_groups]
    for p in pairs:
        group_pairs[group_of[p.unit_id_a]].append(p)

    for group, in_group in zip(raw_groups, group_pairs):
        ordered = sort_cluster(group, in_group)
        group_sims = [p.similarity for p in in_group]
        min_sim = min(group_sims)
        max_sim = max(group_sims)
        clusters.append(
            Cluster(unit_ids=ordered, min_similarity=min_sim, max_similarity=max_sim)
        )

    clusters.sort(key=_avg_similarity, reverse=True)
    return clusters


def _avg_similarity(cluster: Cluster) -> float:
    return (cluster.min_similarity + cluster.max_similarity) / 2


def _similarity(a: int, b: int, pairs: list[SimilarPair]) -> float:
    for p in pairs:
        if (p.unit_id_a == a and p.unit_id_b == b) or (
            p.unit_id_a == b and p.unit_id_b == a
        ):
            return p.similarity
    return 0.0
