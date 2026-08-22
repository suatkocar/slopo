from datetime import datetime

from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.report.markdown import (
    build_cluster_markdown,
    build_index_markdown,
)

_UNITS = {
    1: UnitRecord(1, "src/A.java", "foo", 10, 20, "int foo() {}", "hashA"),
    2: UnitRecord(2, "src/B.java", "bar", 5, 15, "int bar() {}", "hashB"),
}
_CLUSTERS = [Cluster([1, 2], 0.95, 0.97)]
_GENERATED_AT = datetime(2026, 6, 19, 14, 30, 0)


def test_renders_index_with_one_row_per_cluster():
    markdown = build_index_markdown(_CLUSTERS, _UNITS, {}, _GENERATED_AT)

    assert (
        markdown
        == """\
Generated 2026-06-19 14:30:00

| Cluster                   | Hash         | Score     | Code units | Unique files |
|---------------------------|--------------|-----------|------------|--------------|
| [Cluster 1](cluster-1.md) | 925587b7b8ed | 0.95-0.97 | 2          | 2            |
"""
    )


def test_index_counts_exact_duplicates_in_code_units_and_unique_files():
    duplicates = {
        1: [
            UnitRecord(3, "src/C.java", "baz", 1, 11, "int foo() {}", "hashA"),
            UnitRecord(4, "src/A.java", "qux", 2, 12, "int foo() {}", "hashA"),
        ]
    }

    markdown = build_index_markdown(_CLUSTERS, _UNITS, duplicates, _GENERATED_AT)

    assert (
        markdown
        == """\
Generated 2026-06-19 14:30:00

| Cluster                   | Hash         | Score     | Code units | Unique files |
|---------------------------|--------------|-----------|------------|--------------|
| [Cluster 1](cluster-1.md) | 925587b7b8ed | 0.95-0.97 | 4          | 3            |
"""
    )


def test_renders_cluster_with_each_unit_and_its_code_block():
    markdown = build_cluster_markdown(1, _CLUSTERS[0], _UNITS, {})

    assert (
        markdown
        == """\
## (1) score 0.95-0.97

Hash: `925587b7b8ed`

---

- `src/A.java` lines 10-20

```java
int foo() {}
```

---

- `src/B.java` lines 5-15

```java
int bar() {}
```
"""
    )


def test_groups_exact_duplicates():
    duplicates = {1: [UnitRecord(3, "src/C.java", "baz", 1, 11, "x", "hashA")]}

    markdown = build_cluster_markdown(1, _CLUSTERS[0], _UNITS, duplicates)

    assert (
        markdown
        == """\
## (1) score 0.95-0.97

Hash: `925587b7b8ed`

---

- `src/A.java` lines 10-20
- `src/C.java` lines 1-11

```java
int foo() {}
```

---

- `src/B.java` lines 5-15

```java
int bar() {}
```
"""
    )


def test_orders_duplicates_by_file_path():
    units = {1: UnitRecord(1, "src/C.java", "foo", 10, 20, "int foo() {}", "hashA")}
    cluster = Cluster([1], 0.95, 0.97)
    duplicates = {
        1: [
            UnitRecord(2, "src/D.java", "baz", 1, 11, "x", "hashA"),
            UnitRecord(3, "src/A.java", "qux", 2, 12, "y", "hashA"),
        ]
    }

    markdown = build_cluster_markdown(1, cluster, units, duplicates)

    assert (
        markdown
        == """\
## (1) score 0.95-0.97

Hash: `23ae0e263e41`

---

- `src/A.java` lines 2-12
- `src/C.java` lines 10-20
- `src/D.java` lines 1-11

```java
int foo() {}
```
"""
    )


def test_tags_code_fence_by_language_for_tsx_jsx_and_svelte():
    units = {
        1: UnitRecord(1, "src/A.tsx", "foo", 10, 20, "const foo = () => {}", "hashA"),
        2: UnitRecord(2, "src/B.jsx", "bar", 5, 15, "const bar = () => {}", "hashB"),
        3: UnitRecord(3, "src/C.svelte", "baz", 1, 11, "function baz() {}", "hashC"),
    }
    cluster = Cluster([1, 2, 3], 0.95, 0.97)

    markdown = build_cluster_markdown(1, cluster, units, {})

    assert (
        markdown
        == """\
## (1) score 0.95-0.97

Hash: `2960e30a5658`

---

- `src/A.tsx` lines 10-20

```tsx
const foo = () => {}
```

---

- `src/B.jsx` lines 5-15

```jsx
const bar = () => {}
```

---

- `src/C.svelte` lines 1-11

```svelte
function baz() {}
```
"""
    )
