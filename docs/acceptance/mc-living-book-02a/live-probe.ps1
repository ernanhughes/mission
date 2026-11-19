# MC-LIVING-BOOK-02A read-only live probe.
# It reads Mission and ALIVE, plans once, does not call POST /refresh, launches no workflow and
# calls no model. ALIVE may reconcile a live binding's freshness during a read.
param(
    [string]$Alive = "http://127.0.0.1:8000",
    [string]$Mission = "http://127.0.0.1:8790",
    [string]$BookId = "72b95337-795f-5327-87c6-ad67e4246086",
    [string]$ChapterId = "14-chapter.md",
    [string]$ChapterFile = "C:\books\distillation\content\books\distillation\14-chapter.md"
)

$ErrorActionPreference = "Stop"

function Get-Json([string]$Uri) {
    $response = Invoke-WebRequest -Uri $Uri -SkipHttpErrorCheck -TimeoutSec 30
    $body = $null
    if ($response.Content) {
        try { $body = $response.Content | ConvertFrom-Json } catch { $body = $response.Content }
    }
    [pscustomobject]@{ status = [int]$response.StatusCode; body = $body }
}

$missionStatus = Get-Json "$Mission/api/living-book/projects/distillation"
$missionChapter = Get-Json "$Mission/api/living-book/projects/distillation/chapters/$ChapterId"
$missionQuality = Get-Json "$Mission/api/living-book/projects/distillation/quality?chapter_id=$ChapterId"
$book = Get-Json "$Alive/api/v1/living-books/$BookId"
$workspaceId = $book.body.workspace_id
$workspace = Get-Json "$Alive/api/v1/workspaces/$workspaceId"
$plan = Get-Json "$Alive/api/v1/workspaces/$workspaceId/workflows/plan?chapter_path=content%2Fbooks%2Fdistillation%2F14-chapter.md"
$experience = Get-Json "$Alive/api/v1/workspaces/$workspaceId/experience?chapter_path=content%2Fbooks%2Fdistillation%2F14-chapter.md&criteria=economy"
$improvements = Get-Json "$Alive/api/v1/workspaces/$workspaceId/improvements"
$memory03 = Get-Json "$Alive/api/v1/workspaces/$workspaceId/experience/relevant?objective=chapter%2014%20economy"
$catalogue = Get-Json "$Alive/api/v1/workflows/chapter-improvement"

$prose = $missionQuality.body.measures | Where-Object { $_.id -eq "mission.prose.manuscript-prose-v1" }
$technical = $missionQuality.body.measures | Where-Object { $_.id -eq "mission.technical.claims" }
$publication = $missionQuality.body.measures | Where-Object { $_.id -eq "mission.publication.readiness" }
$chapter = $book.body.chapters | Where-Object { $_.chapter_id -eq $ChapterId } | Select-Object -First 1
$versions = @($catalogue.body.versions | ForEach-Object { $_.version })

$result = [pscustomobject]@{
    captured_at = (Get-Date).ToUniversalTime().ToString("o")
    urls = @{ mission = $Mission; alive = $Alive }
    mission = @{
        status = @{
            http = $missionStatus.status
            state = $missionStatus.body.state
            book_id = $missionStatus.body.book.id
            workspace_id = $missionStatus.body.book.workspace_id
            source = $missionStatus.body.book.source
            model = $missionStatus.body.book.model
        }
        chapter = @{
            http = $missionChapter.status
            chapter_id = $missionChapter.body.chapter_id
            title = $missionChapter.body.title
            sha256 = $missionChapter.body.sha256
            word_count = $missionChapter.body.word_count
            rendered_characters = $missionChapter.body.markdown.Length
        }
        quality = @{
            http = $missionQuality.status
            coverage = $missionQuality.body.coverage
            prose = @{
                status = $prose.status
                rubric = $prose.rubric
                model = $prose.model
                observed_at = $prose.observed_at
                overall = $prose.value.overall
                economy = $prose.value.dimensions.economy
                limitations = $prose.limitations
            }
            technical = @{ status = $technical.status; chapter = $technical.value.chapter }
            publication = @{ status = $publication.status; detail = $publication.detail }
        }
    }
    alive = @{
        book = @{
            http = $book.status
            workspace_id = $workspaceId
            ready = $book.body.ready
            source = $book.body.source
            chapter = $chapter
        }
        workspace_sources = $workspace.body.sources
        plan = @{
            http = $plan.status
            mode = $plan.body.mode
            workflow_version = $plan.body.workflow_version
            model_calls = $plan.body.model_calls
            output_tokens = $plan.body.output_tokens
            wall_seconds = $plan.body.wall_seconds
            sha256 = $plan.body.sha256
            error = if ($plan.status -ge 400) { $plan.body.error.message } else { $null }
        }
        experience = @{
            http = $experience.status
            enabled = $experience.body.retrieval.enabled
            eligible_candidates = $experience.body.retrieval.eligible_candidates
            selected = $experience.body.retrieval.selected
            context_sha256 = $experience.body.retrieval.context_sha256
        }
        improvements = @{
            http = $improvements.status
            counts = $improvements.body.counts
        }
        memory03_route = @{
            http = $memory03.status
            message = if ($memory03.status -ge 400) { $memory03.body.error.message } else { $null }
        }
        workflow_catalogue = @{
            http = $catalogue.status
            versions = $versions
            has_v6 = ($versions -contains 6)
            has_v801 = ($versions -contains 801)
        }
        local_chapter_file = @{
            path = $ChapterFile
            sha256 = (Get-FileHash $ChapterFile -Algorithm SHA256).Hash.ToLower()
            bytes = (Get-Item $ChapterFile).Length
        }
    }
}

$output = Join-Path $PSScriptRoot "live-probe.json"
$result | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 $output

[pscustomobject]@{
    output = $output
    mission_state = $result.mission.status.state
    chapter_sha256 = $result.mission.chapter.sha256
    local_file_sha256 = $result.alive.local_chapter_file.sha256
    plan_http = $result.alive.plan.http
    plan_error = $result.alive.plan.error
    workspace_approval = $result.alive.workspace_sources[0].approval_ref
    current_approval = $result.alive.book.source.approval_ref
    experience_eligible = $result.alive.experience.eligible_candidates
    memory03_http = $result.alive.memory03_route.http
    workflow_versions = ($result.alive.workflow_catalogue.versions -join ",")
} | Format-List
