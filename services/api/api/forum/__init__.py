"""The course x instructor forum (SPEC "Forum", prompt 08).

A forum *page* is a `course_instructor` row (`page_id` = `course_instructor.id`). Every stored
author, voter and reporter reference is `api.auth.hashing.author_ref(account_id, page_id)`, so
rows on two pages cannot be joined to one account without the server key.
"""
