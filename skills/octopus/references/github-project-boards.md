# Creating a GitHub Project V2 Board (Zero Red Workflows)

Follow this playbook whenever creating a new GitHub Project V2 board for a repository or
product so it starts with **OTF-aligned stages, custom fields, views, and working green
workflows** — without hitting GitHub's API quirks.

## Hard Invariant: Clone a Blueprint — Never Mutate Default `Status` via API

- **DO NOT** create a blank project and call `updateProjectV2Field` on its `Status` options.
  GitHub's GraphQL API replaces all option IDs with new random IDs, which breaks all 5 built-in
  workflows (`Auto-close issue`, `Item added to project`, `Item closed`, `Pull request linked`,
  `Pull request merged`) and turns them red `(!)`.
- **DO** clone an existing green blueprint with `gh project copy` (`--drafts=false` by default,
  so zero issues are copied — only columns, fields, views, and working green workflows).

### Available Blueprints (`alexsmedile`)

| Blueprint | Project # | OTF Stage Recipe | Columns (`inactive \| active \| closed`) | Best For |
|---|---|---|---|---|
| **Linear** | `#3` (`Planar`) | `linear` | `Triage, Backlog \| Todo, In Progress, In Review \| Done, Canceled` | Software repos, SaaS products, PR-driven engineering |
| **Octopus** | `#1` (`Tasks`) | `octopus` | `Backlog, Paused \| Next, Now, In Review \| Done, Dropped` | Personal catch-all / life / multi-area task hubs |

*(Requires `gh` token with `project` scope; if missing, run `gh auth refresh -s project`.)*

---

## Step-by-Step Board Creation

### 1. Clone the blueprint

```bash
gh project copy 3 \
  --source-owner alexsmedile \
  --target-owner alexsmedile \
  --title "<Board Title>" \
  --format json
```

Record the returned `id` (`PVT_...`), `number` (`<N>`), and `url`.

### 2. Link repository & verify workflows

```bash
# Get repo node ID
gh api graphql -f query='query { repository(owner: "alexsmedile", name: "<repo>") { id } }'

# Link repo to the new project
gh api graphql -f query='mutation {
  linkProjectV2ToRepository(input: { projectId: "<PVT_ID>", repositoryId: "<REPO_ID>" }) {
    repository { nameWithOwner }
  }
}'
```

### 3. Add `agent-ready` label (for `plan-to-issues` overnight PRs)

```bash
gh label create "agent-ready" \
  --repo alexsmedile/<repo> \
  --color "0E8A16" \
  --description "Clear acceptance criteria & test command; safe for unattended agent Draft PR" \
  --force
```

### 4. Attach existing open issues (in small batches)

- Query open issues (`issues(first: 50, states: OPEN) { nodes { id number title } }`).
- **Batch size limit:** Never send >5–8 `addProjectV2ItemById` or `updateProjectV2ItemFieldValue`
  mutations in a single GraphQL request (larger batches trigger GitHub HTTP 502 timeouts).
- Default existing backlog/proposal/deferred issues to **`Backlog`** (`state: inactive`) so
  `Todo` stays focused on committed work.

### 5. Write `.otf/profile.yaml` in the repository

Apply the matching OTF stage recipe and set `discovery.remote`:

```bash
otf templates apply linear --file <repo>/.otf/profile.yaml
```

Ensure `discovery.remote` points to `system: "github"`, `scope: "alexsmedile/<repo>"`, and
`project: <N>`, with `authority: { default: "github", stage: "github-projects" }`.

### 6. One optional UI step (Auto-add)

Repo-specific `Auto-add to project` rules do not copy across clones:
- **Primary repo:** In GitHub UI → **Workflows** → **`Auto-add to project`** → select `alexsmedile/<repo>` (`is:issue is:open`) → toggle **On**.
- **Secondary repos on a multi-repo board** (Free/personal plan allows 1 built-in `Auto-add`):
  use `otf push <task> github:alexsmedile/<repo> --project <N> --apply` or add a lightweight
  `.github/workflows/add-to-project.yml` using `actions/add-to-project@v1`.
