# knowledge-base: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Global support suite · tier `common` (every academy type enables it)

## Purpose

Articles, FAQs and how-to guides for self-service (`module.yaml`). The knowledge base is the organisation's
library of help content (how to reset a password, connect to campus Wi-Fi, request a transcript, use the LMS)
so that people can solve problems themselves, and support staff can point a helpdesk ticket to an answer.
Category names, tags and wording are the organisation's own; nothing in the module assumes one kind of academy.
The contract is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

## Users and what they need

| Role (profile role → module role) | Needs | Dashboard widget |
|---|---|---|
| Every signed-in person: student, faculty, staff, applicant (→ `knowledge-base-reader`) | Browse, search and read published articles meant for everyone; say whether an article helped | — |
| Support Staff (`support-staff` → `knowledge-base-author`) | Also read staff-only articles; write and edit drafts, submit them for review; see feedback and usage | `knowledge-base.top-articles` (`GET /stats/top-articles`) |
| Org admin (`org-admin` → `knowledge-base-editor`), and any support lead the organisation assigns the role to | Everything an author does, plus review, return, publish, archive and restore articles, and manage categories | `knowledge-base.top-articles` |
| Management (`management` → `knowledge-base-viewer`) | Read every published article, including staff-only, and see usage | — |

## Article types and audiences

- **Types:** `article` (general explanation), `faq` (the title is the question, the body the answer), `how_to`
  (step-by-step guide; numbered steps are written in the body). Types share one lifecycle and are used for browsing,
  filtering and display.
- **Audiences:** `everyone` (every signed-in reader) or `staff` (support staff, leads and management; for internal
  procedures). Audience is part of an article's content, so changing it goes through a revision.

## Main flows

1. **Set up categories.** An editor creates a two-level category tree with a display order. A category can be
   renamed, moved, reordered or deactivated; one that holds published articles cannot be deactivated.
2. **Create.** An author creates an article: type, title, summary, body (Markdown), category, tags, audience,
   related articles and optional references. It gets a slug unique in the organisation and revision 1 as a draft.
3. **Edit.** Content always lives in revisions, and an article has at most one open revision (`draft` or
   `in_review`). Saving an open draft replaces its content and needs every content field. When there is no open
   revision, a new draft is started from a source revision: the one named by `from_revision` (rollback), otherwise
   the published revision, otherwise the latest revision. Fields left out are copied from the source, so a rollback
   is `PUT /articles/{id}/draft?from_revision=n` with an empty body. Readers keep seeing the published revision until
   the new one is published.
4. **Submit for review.** The author submits their own draft (`draft → in_review`). Editors are notified through
   notification; no public event is published (open question 7).
5. **Return.** An editor returns the revision with a comment (`in_review → draft`). The author is notified through
   notification; no public event is published. A revision in review cannot be edited until it is returned.
6. **Publish.** An editor publishes the open revision, from `draft` or `in_review` (open question 3). It becomes the
   published revision, the previous one becomes `superseded`, and the article is `published`. Publishes
   `knowledge-base.article.published`.
7. **Discard.** The open revision can be discarded (its state becomes `discarded`); the published revision, if any,
   is unaffected.
8. **Archive and restore.** An editor archives a draft or published article with a reason; an open draft is kept.
   Archived articles leave browse and search but stay readable by id with status `archived`, so links from helpdesk
   tickets never break. Restore returns the article to `published` if it was ever published, otherwise to `draft`.
   Archiving publishes `knowledge-base.article.archived`; restoring a published article publishes
   `knowledge-base.article.published` again.
9. **Browse and search.** Readers browse by category, type and tag, and search with `GET /articles?q=`; results
   carry a short highlighted snippet. Readers only ever receive published articles whose audience they may read.
10. **Feedback.** A reader says whether an article helped, with an optional comment. One vote per person per article;
    voting again replaces the earlier vote. Articles keep helpful and not-helpful counts. Comments are visible only to
    authors, editors and viewers.
11. **Keep content fresh.** Each article has a `review_by` date. It can be set when the article is created, on
    publish, or in the article settings. Publishing without a `review_by` keeps an existing date; only an article that
    has none gets `KNOWLEDGE_BASE_DEFAULT_REVIEW_MONTHS` from the publication date. An article is stale when the date
    has passed, worked out when read; authors and editors filter for stale articles. There are no reminders in v1.
12. **Link from helpdesk.** Support staff link a ticket to an article through helpdesk's own links
    (`{module: knowledge-base, entity: article, ref_id}`). Helpdesk owns the link; the knowledge base stores nothing
    about tickets.

### Statuses

```
Article:   draft → published → archived
           draft → archived;  archived → published (if it was ever published) or draft  (restore)

Revision:  draft → in_review → published → superseded
           in_review → draft (returned);  draft or in_review → discarded
           draft → published (editor publishes directly)
```

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`. Search data
  for articles is kept per organisation.
- Every state change writes an audit record through `packages/sdk`: articles, revisions (create, edit, submit,
  return, publish, discard), archive, restore, article settings, categories.
- Audience is enforced on the server in every read, list, search and statistics query.
- A revision cannot be changed once it leaves `draft`. Nothing is deleted: articles are archived, revisions superseded
  or discarded, categories deactivated.
- Feedback is accepted only on published articles. Comments are visible only with `knowledge-base:stats:read`.
- A view is counted at most once per reader per article per day and stored as daily totals per article; no
  per-person reading history is kept.
- Article bodies are Markdown text. Embedded HTML and scripts are not rendered.
- References to other modules use `{module, entity, id}` by id only, with no foreign keys and no check against the
  other module.
- Event payloads carry ids, slug, revision number, type, category and audience only, never titles, bodies, feedback
  comments or reader ids.
- No dependency on another module being enabled. No real data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Category | id, parent_id (null = top level), name, description, position, active |
| Article | id, slug, status (draft, published, archived), owner_id, review_by, published_revision_no, open_revision_no, view_count, helpful_count, not_helpful_count, first_published_at, published_at, archived_at |
| Revision | article_id, revision_no, state (draft, in_review, published, superseded, discarded), type, title, summary, body, category_id, tags, audience, related_article_ids, references, author_id, change_note, submitted_at, reviewed_by, review_comment, created_at |
| Feedback | article_id, person_id, helpful, comment, revision_no, created_at (one per person per article) |
| Reference | module, entity, id, note (stored on a revision) |
| ArticleViewDay | article_id, date, views |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `knowledge-base.top-articles` | Support Staff | `GET /stats/top-articles?period=7d\|30d\|90d&metric=views\|helpful` | `knowledge-base:stats:read` | Published articles ranked by views in the period (default) or by helpful share (only articles with at least `KNOWLEDGE_BASE_HELPFUL_MIN_VOTES` votes), with views, helpful share and not-helpful count |

The widget itself is built in week 2 or later in `frontend/src/widgets/`; this PR only fixes the endpoint.

## Events

| Event | What it is for | Current consumers |
|---|---|---|
| `knowledge-base.article.published` | The content readers see changed: first publication, republication, or restore of a published article. Intended for search indexing once the engine is decided, and for modules that show linked articles. | None yet (open question 1) |
| `knowledge-base.article.archived` | An article left browse and search. Intended for removing it from a search index, and for showing linked articles as archived. | None yet (open question 1; a helpdesk reaction would need a helpdesk change) |

The review workflow (submit, return) is internal: the module notifies editors and authors itself through notification
and records each step in audit, but publishes no public event for it (open question 7).

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | anyone | the two events above (`events.yaml`) |
| Consumes | none in v1 | |
| Platform | identity, audit, notification | through `packages/sdk`: permission checks; audit; review notices to editors and authors (internal, no public event) |
| Search | `platform/search` | Not a dependency in v1: it has no contract yet. `GET /articles?q=` is this module's search contract; the engine behind it is open question 1 |
| Linked from | helpdesk | Helpdesk stores ticket links to articles; this module guarantees stable article ids and keeps archived articles readable by id. `GET /articles?q=` can serve article suggestions in helpdesk later |
| References | incident-management | An article may reference a problem (`{module: incident-management, entity: problem, id}`), for example a known-error workaround. No incident events are consumed |

## Configuration

`config/env.example`: `KNOWLEDGE_BASE_DEFAULT_REVIEW_MONTHS`, `KNOWLEDGE_BASE_TOP_ARTICLES_LIMIT`,
`KNOWLEDGE_BASE_HELPFUL_MIN_VOTES`.

## Out of scope (v1)

- Helpdesk tickets and the links on them (helpdesk); incidents, problems and RCAs (incident-management).
- Public website pages, news and notices (`web-portal-cms`); course content (`lms`); the library catalogue and
  digital library (`library`).
- The search engine and file storage themselves (`platform/search`, `platform/documents`).
- Attachments and images in articles (open question 2).
- Audiences beyond `everyone` and `staff`.
- AI or chatbot answers, translation into other languages, discussion threads on articles.
- Reminders for review dates; the scheduler is not used in v1.

## Open questions (for review)

1. **Search engine (Himanshu).** `platform/search` has no contract. `GET /articles?q=` is the stable module contract.
   Should v1 search the module's own data until the platform service exists, and would indexing then consume
   `article.published` and `article.archived` or use a push API?
2. **Attachments and images (Himanshu).** `platform/documents` has no contract, so v1 has no attachments. Add them
   when that contract exists?
3. **Review.** Must every publication go through `in_review`, or may editors publish a draft directly (this draft)?
   Should an organisation be able to switch review off?
4. **Top-articles metric.** Views by default with a helpful option (this draft)? Which default period?
5. **Linked-ticket counts.** "Most linked from tickets" would need helpdesk to publish a link event (a helpdesk change
   in its own PR). Is it wanted?
6. **Known errors.** Manual articles with a problem reference (this draft), or should incident-management's events
   later carry enough content to draft articles?
7. **Revision workflow events.** Submitting and returning a revision are internal in v1: notices go through
   notification and the steps are audited, but no public event is published because no module needs one. If a module
   later needs them, `knowledge-base.revision.submitted` and `knowledge-base.revision.returned` can be added without
   breaking the contract.
8. **Feedback alerts.** Should an article's owner be notified of "not helpful" feedback with a comment? That would add
   a feedback event.
9. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each
   payload and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the
   envelope only and declares `version` on every event. How will existing contracts move to it?
10. **Role convention (Faizan).** Module roles (`knowledge-base-author`) mapped to profile roles, or roles named after
    profile roles (`support-staff`), as for the other support modules? Profiles have no support-lead role, so this
    draft maps `org-admin` to `knowledge-base-editor` so that at least one profile role can publish; should a
    support-lead profile role exist?
11. **Public FAQs.** Confirm that FAQs for people who are not signed in belong to `web-portal-cms`, not here.
