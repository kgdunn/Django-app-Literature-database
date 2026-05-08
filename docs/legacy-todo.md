# Legacy `todo.txt` (archived 2026-05-08)

Preserved verbatim from the 2010-era repository root. Items are folded into the revival roadmap in [CLAUDE.md](../CLAUDE.md) and tracked as GitHub issues going forward; this file exists for provenance.

```
Code up the use of "allow PDF" to be downloaded in the data model

Put a link to bitbucket source of this application
Add a License file to the add
Add a requirements file to the app, with the right version of haystack install

Move the footer to the bottom of the page always
Mobile friendly test?
Log the page visits to the logfile too

Make the top N pages, top tags, etc in a django queue that runs daily; save that to DB; front page rendering speed will improve then


Make the index realtime

Check if you can add new items now

Correct all references in PID to the new site

Redirect all old literature.connectmv.com -> learnche.org/literature

Add Google analytics
```

## Mapping to revival phases

| Original todo                                  | Status / phase |
| ---------------------------------------------- | -------------- |
| "allow PDF" download flag in data model        | already exists (`Item.private_pdf` + `Item.can_show_pdf`); Phase 5 decides whether to keep them |
| Link to source                                 | now in repo metadata + README.md |
| License file                                   | already exists (`LICENSE`) |
| Requirements file with pinned Haystack         | superseded — Phase 0 adds `pyproject.toml` (uv); Haystack is dropped in Phase 3 in favour of Postgres FTS |
| Footer at bottom of page                       | Phase 6 (templates modernization) |
| Mobile-friendly                                | Phase 6 |
| Log page visits to logfile                     | Phase 4 + Phase 2 (LOGGING dict to stdout, captured by `docker logs`) |
| Pre-computed top-N caches                      | Phase 6 (cache table + nightly management command) |
| Real-time search index                         | Phase 3 (Postgres FTS triggers update on save automatically) |
| New-item submission                            | Phase 1 (Django admin will work once the Py3 port lands) |
| References in *Process Improvement using Data* | external — track separately |
| Redirect `literature.connectmv.com` → new host | Phase 9 (Caddy redirect block) |
| Google Analytics                               | deferred — privacy stance unchanged from openmv (no third-party trackers) |
