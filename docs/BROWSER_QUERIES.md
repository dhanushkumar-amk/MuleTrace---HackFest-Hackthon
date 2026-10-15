# FalkorDB Browser queries

Open the browser at **http://localhost:3000** (run `docker compose up -d` first) and
paste any query below. Graph = `muletrace`. Read the data with these ready-to-paste
queries.

## 1. Ravi and everything within 3 hops (the victim + nearby mules)
```cypher
MATCH p=(a:Account {id:'ACC_0461'})-[*1..3]-(b)
RETURN p
```

## 2. The full Ring 1 chain: Ravi → A → B / C → D → E (money forward)
```cypher
MATCH p=(a:Account {id:'ACC_0461'})-[:PAID*1..6]->(b:Account)
RETURN p
```

## 3. The shared device linking Ring 1's Mule B to Ring 2
```cypher
MATCH p=(:Account {id:'ACC_0463'})-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(o:Account)
RETURN p
```

## 4. The decoy and its neighbours (all its payers + suppliers)
```cypher
MATCH p=(a:Account {id:'ACC_0476'})-[:PAID]-(n)
RETURN p
```

## 5. Ring 3 fan-in: funders → collectors → hub (ACC_0475)
```cypher
MATCH p=(f)-[:PAID]->(c)-[:PAID]->(h:Account {id:'ACC_0475'})
RETURN p
```

## 6. The 10 busiest accounts (most incoming payments)
```cypher
MATCH (a:Account)<-[p:PAID]-()
RETURN a.id, a.holder_name, count(p) AS incoming
ORDER BY incoming DESC LIMIT 10
```

## 7. Ravi's fraud report
```cypher
MATCH (f:FraudReport)-[:REPORTS_VICTIM]->(v:Account {id:'ACC_0461'})
RETURN f
```