"""The annual catalog pipeline (SPEC "Data ingestion", prompt 09).

fetch -> snapshot -> parse -> validate -> diff -> human review -> publish. Plain code parses
everything structured (course blocks, links, counts); agents E1-E4 read only prose. Nothing
here publishes: results become `review_item` rows and `program_version` rows in status
`review`, and a curator publishes from `/admin/review`.

Modules:
    settings    IngestSettings (CATALOG_INGEST_ENABLED, contact address, cost cap, MinIO)
    snapshots   raw responses in object storage (MinIO, S3 API) + `source_snapshot` rows
    crawler     robots.txt, 1 request per second, honest user agent
    courseleaf  HTML -> links, page text, course blocks (stdlib parser only)
    courses     course blocks -> staged course / crosslist / relation rows and their diff
    catalog     CatalogView: the courses and course lists an agent may name
    compare     node-level agreement between two rule trees
    validators  checks (a)-(g)
    e1 e2 e3 e4 the four ingestion agents
    golden      golden plans against a candidate rule tree
    pipeline    one program end to end; the annual run
    records     ReviewDraft / VersionDraft and the database writer
    jobs        the Arq cron jobs (annual run, monthly change check)
    pilot       `make ingest-pilot`
"""
