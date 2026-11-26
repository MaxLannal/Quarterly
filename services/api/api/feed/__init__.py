"""The Catalog page's browse rows (`GET /catalog/browse`, issue #19), which replaced the Feed.

- `categories`: the subject families of the spotlights (every catalog subject maps to one).
- `text`: excerpts and plain text from markdown (no model involved).
- `pool`: the catalog's spotlight-worthy courses, cached per database and catalog year.
- `service`: the course spotlights and the student quotes.
- `new_courses`: newly released courses (`data/catalog/new_courses.yaml`, or a second catalog
  year).
"""
