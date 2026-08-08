# Design for Combinatorial Maximum

Status: architectural law for GymAct v26.8.7+

GymAct does not optimize by choosing early. It optimizes by preserving the largest
bounded set of lawful reversible possibilities until consequence forces a cut.

## 1. Canonical object

The canonical decision object is a public-semantic possibility graph:

```text
G = (O, M)
```

where `O` are typed objects and `M` are typed morphisms. Runtime Python models are
lossless projections of that graph; they are not an independent source of truth.

Important objects include admitted observations, subjects, capabilities, actions,
planners, plans, providers, verifiers, policies, processes, controllers and receipts.

Important morphisms include observe, admit, enable, plan, realize, manufacture,
project, verify, replay, reuse and actuate.

## 2. Preserve before select

For an admitted observation `O*`, GymAct SHALL construct the bounded lawful ecology
before selecting a consequential edge. The conceptual possibility space is:

```text
P = D × Pi × Theta × E × V × A × C × ...
```

where dimensions may include domains, planners, parameters, effectors, verifiers,
authority classes and controllers.

A layered possibility graph SHOULD represent this product compactly: graph size may
grow with the sum of alternatives while path cardinality represents their product.

No new planner, provider, verifier or controller SHALL replace an existing lawful
alternative solely because it is newer or locally faster.

## 3. Reversibility is admission, not optimism

The reversible closure contains only morphisms mechanically classified `REVERSIBLE`.

```text
COMPENSATABLE != REVERSIBLE
UNKNOWN != REVERSIBLE
IRREVERSIBLE != REVERSIBLE
```

Unknown reversibility is a fence. Compensation is a separate topology. An edge that
cannot enter reversible closure remains represented and evidenced; it is not erased.

## 4. Failed edge is topology

A refused, blocked, stale or unsupported edge does not falsify sibling possibilities.

```text
failed(edge_i) != failed(G)
```

Every edge evaluation is retained with its typed disposition. This permits the graph
to learn topology from failure rather than collapsing to a binary workflow outcome.

## 5. Explicit bounds

Combinatorial maximalism is bounded by ontology, capability, authority, cost and
evidence. Every practical exploration SHALL expose explicit limits such as depth,
paths, combinations, cost, wall time, compute, human intervention and risk.

If a bound truncates exploration, truncation is evidence. Silent pruning is forbidden.

## 6. Structural scan before interpretation

The first selector pass is structural and cheap:

```text
G -> structural_scan(G) -> sigma(G)
```

The structural signature includes topology, object/morphism classes, phases,
reversibility, standing, branching and cycle information without requiring semantic
interpretation of every node.

Semantically different graphs with the same relevant structure MAY share a structural
index key while retaining different content-addressed graph identities.

## 7. Applicability before ranking

Ranking cannot manufacture applicability.

```text
P_eligible = {p in P | requirements(p) subset admitted_context}
```

The empirical index receives the current eligible combination identities as input.
Records outside that set cannot win ranking regardless of historical performance.

Only after applicability filtering may the system retrieve a Pareto frontier over cost,
latency, compute, intervention, risk, confidence and value. No single universal best
planner or provider is assumed.

## 8. SELECT, CONSTRUCT and DO

The authority partition is strict:

```text
SELECT      powerless
CONSTRUCT   powerless
DO          consequential
```

The possibility graph SHALL NOT contain a live `ExecutionGrant`. Planner output,
model output, cached recipes, graph queries and hooks manufacture candidates or
intents only.

## 9. Irreversible frontier

Exploration never traverses a DO edge. It ends at an explicit irreversible frontier:

```text
R(O*) -> F_DO
```

Even when a grant reference exists, the explorer reports an admitted frontier; it does
not execute it.

Selection is a separate cut operation that binds:

- exact possibility graph digest;
- exact reversible path identity;
- exact DO morphism identity;
- action and capability identity;
- subject identity;
- prepared action digest;
- execution grant digest;
- selector identity;
- selection basis/evidence.

Only then may BRCE receive a request.

## 10. Exclusive consequence path

The canonical consequential path is:

```text
public RDF graph
  -> SHACL admission
  -> lossless runtime projection
  -> structural scan
  -> maximal proven-reversible closure
  -> explicit irreversible cut
  -> ExecutionGrant admission
  -> BRCE
  -> provider effect
  -> independent observation
  -> verification
  -> cut-bound receipt
```

The legacy `BrokerRequest` path is compatibility. New production interfaces SHALL use
`CombinatorialBrokerRequest`.

## 11. Receipt standing

A consequential DCM receipt binds the decision topology as well as the effect:

```text
R = H(G, path, morphism, selection, authority, effect, O', V, parents)
```

Replay can therefore detect a changed ecology or changed irreversible choice even when
the final API call or external state happens to look equivalent.

## 12. Public ontology law

Possibility authority uses public RDF semantics. Current projection uses PROV-O,
DCTERMS, SKOS and SHACL; additional mappings SHOULD prefer P-PLAN, ODRL, QUDT,
SOSA/SSN, EARL, DQV and OWL-Time when those semantics are required.

`urn:gymact:*` resources may identify ABox objects, SKOS concepts and SHACL shapes.
GymAct-owned RDF/OWL predicates and classes are forbidden unless public vocabulary
cannot lawfully represent the requirement.

## 13. Cognition compilation

The canonical HOT artifact is not a cached action candidate. It is a compiled graph
route:

```text
(graph identity, reversible path, DO frontier, prior receipts)
```

On reuse, the route is re-admitted against the current graph. Authority is never cached
and is minted fresh at the irreversible cut.

Thus repeated cognition becomes an index into proven causal structure rather than an
ambient execution shortcut.

## 14. Algebraic laws

Reversible path composition obeys identity and associativity where endpoints match.
Non-adjacent paths do not compose by analogy.

```text
id_A ; f = f
f ; id_B = f
(f ; g) ; h = f ; (g ; h)
```

Costs compose according to their declared objective algebra; verification confidence is
currently bottlenecked by the least-confident component.

## 15. Falsifiers

The DCM architecture is falsified if any canonical path:

1. selects one planner/provider before preserving other lawful reversible alternatives;
2. traverses an `UNKNOWN`, `COMPENSATABLE` or `IRREVERSIBLE` edge as reversible;
3. silently prunes due to resource bounds;
4. allows a failed edge to erase unrelated alternatives;
5. ranks a combination not admitted by the current applicability set;
6. stores live execution authority in the possibility graph or a compiled route;
7. traverses a DO edge during exploration;
8. executes without a content-bound irreversible cut;
9. emits a consequential receipt that cannot identify its graph/path/DO selection;
10. replay accepts missing or drifted DCM identity when an exact identity is expected;
11. makes Python schemas canonical over the public RDF graph;
12. compiles cognition into an executable candidate instead of a re-admitted graph route.

## 16. Operational correspondence

The intended correspondence is:

```text
public ontology graph
  -> indexed query
  -> ggen manufacture
  -> formal admission
  -> runtime projection
  -> DCM court
  -> BRCE
  -> receipt DAG
  -> replay
  -> release standing
```

Each arrow must be mechanically testable. A shortcut is not an optimization unless it
preserves the same graph identity, admission, authority, consequence and verification
semantics.
