---
name: dingtalk-docs
description: Upload existing local files into DingTalk Docs by controlling an already open browser session through chrome-devtools MCP. Use when Codex needs to sync generated reports, incident postmortems, weekly reports, runbooks, meeting notes, or other local documents into a user-specified DingTalk Docs folder.
---

# DingTalk Docs Publisher

Use this skill to upload already generated local files into DingTalk Docs while keeping content generation and destination decisions outside this skill.

This skill is intentionally generic:

- Do not generate business content here.
- Do not assume a specific project.
- Do not hardcode folder names unless the caller explicitly provides them.
- Do not create a new browser login session if an existing logged-in DingTalk page can be reused.

## What This Skill Owns

This skill owns only the file upload step:

- Reuse an already open browser session
- Navigate to DingTalk Docs
- Enter a caller-provided target folder
- Upload a caller-provided local file
- Return upload status and document URL when available

This skill does not own:

- report generation
- incident analysis
- metric aggregation
- local markdown rendering rules
- business folder selection
- report naming policy

## Expected Inputs

Collect or infer these values before using the workflow:

- `local_file_path`
- `target_folder_name` or `target_folder_path`
- `if_exists`
  - `keep_both`
  - `replace`
  - `skip`
- optional `expected_title`

Prefer explicit file upload over editor typing. This skill should not convert Markdown into rich text by pasting body text into the editor unless the user explicitly asks for that fallback.

## Browser Assumptions

Use `chrome-devtools` MCP against the browser that is already open.

Default assumptions:

- DingTalk may already be logged in
- The desired folder may be reachable from:
  - recent pages
  - left navigation
  - search
  - favorites / 收藏
- The desired folder may open in a file list view with `Upload` capability

Prefer reusing an existing DingTalk Docs tab. Open a new tab only if no suitable DingTalk Docs page is already available.

## High-Level Workflow

1. Inspect open pages and reuse an existing DingTalk Docs tab if possible.
2. Navigate to DingTalk Docs if needed.
3. Dismiss onboarding popups, guide masks, and modal dialogs before interacting with the page.
4. Go to the requested folder supplied by the caller.
5. Inspect whether a same-name file or document already exists in that folder.
6. Follow the requested `if_exists` behavior:
   - `keep_both`: upload directly and let DingTalk keep both versions
   - `replace`: delete/rename old one only if the UI supports a reliable replace path; otherwise stop and report
   - `skip`: stop if a same-name item already exists
7. Use folder-level upload or import flow to upload the local file.
8. Wait for upload/import to finish and ensure the new file appears in the folder list.
9. Open the uploaded file only when needed to capture a stable URL.
10. Report the result clearly.

## Folder Navigation Strategy

Do not assume one fixed UI path. Use the most reliable route available in the current session:

1. Favorites / 收藏
2. Search box
3. Left navigation tree
4. Breadcrumb backtracking from an already open document in the same area

When the caller gives a folder name such as `云平台故障记录（2026）` or `平台运行情况`, treat it as a human-visible label, not a path ID.

If multiple folders have the same name:

- prefer the one in the currently active account/workspace
- prefer the one under favorites if the user explicitly said it is in favorites
- otherwise stop and report the ambiguity

## Upload Rules

When uploading a file:

- prefer the caller-provided local file path as the source of truth
- prefer `.md` files when the upstream skill already generated Markdown
- preserve the original file name unless the caller explicitly requests renaming
- use DingTalk's upload or import entry instead of editor typing whenever possible

If DingTalk imports `.md` as an online doc preview rather than a raw attachment, accept that behavior. The skill should not try to re-render the Markdown itself.

## Validation Checks

Before finishing, verify:

- the correct folder was opened
- the uploaded item name matches the local file name or expected title
- the uploaded item appears in the folder list
- the resulting page URL is captured if available

## Failure Handling

If something goes wrong, prefer recoverable retries in this order:

1. close popup / guide overlay
2. re-focus the correct tab
3. re-open the folder
4. retry upload once

Stop and report instead of looping when:

- the account is not logged in
- the target folder cannot be uniquely identified
- permissions prevent upload
- the upload UI changed enough that the target controls cannot be found reliably

## Output Contract

Return a compact result with:

- `success`
- `action`
  - `uploaded`
  - `skipped`
  - `failed`
- `local_file_path`
- `target_folder`
- `document_url` if available
- `notes`

## Project Integration Pattern

When another skill needs DingTalk publishing, keep responsibilities separated:

1. upstream skill generates the local file
2. upstream skill decides the destination folder
3. upstream skill hands `local_file_path` and `target_folder_*` to this skill
4. this skill uploads the file to DingTalk Docs
5. upstream skill decides whether to store the returned URL in local metadata

Examples:

- `incident-management` generates a local incident report or annual summary, decides the corresponding yearly incident folder, then uses this skill to upload the `.md` file
- `weekly-report-generation` generates a local weekly report, decides the weekly reports folder, then uses this skill to upload the `.md` file

## Usage Notes

- Prefer text snapshots over screenshots when using `chrome-devtools`.
- Use the latest snapshot before clicking or filling controls.
- Prefer file upload controls over editor interactions.
- Expect DingTalk file lists and upload dialogs to be dynamic; after each major navigation, take a fresh snapshot.
