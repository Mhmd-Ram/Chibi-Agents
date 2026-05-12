param(
    [Parameter(Position=0)] [string] $Command = "thinking",
    [Parameter(Position=1)] [string] $Arg1,
    [Parameter(Position=2)] [string] $Arg2
)

$ErrorActionPreference = "Stop"
$HostName = if ($env:CHIBI_HOST) { $env:CHIBI_HOST } else { "127.0.0.1" }
$Port     = if ($env:CHIBI_PORT) { $env:CHIBI_PORT } else { "47821" }
$Url      = "http://${HostName}:${Port}/event"

function Post-Event($body) {
    Invoke-RestMethod -Method Post -Uri $Url -ContentType 'application/json' -Body $body | Out-Null
}

switch ($Command) {
    "thinking"       { Post-Event '{"type":"prompt_submit"}' }
    "stop"           { Post-Event '{"type":"stop"}' }
    "notification"   { Post-Event '{"type":"notification"}' }
    "tool"           {
        $tool = if ($Arg1) { $Arg1 } else { "Read" }
        Post-Event (@{ type = "tool_start"; tool = $tool } | ConvertTo-Json -Compress)
    }
    "subagent_start" {
        $agent = if ($Arg1) { $Arg1 } else { "Explore" }
        $id    = if ($Arg2) { $Arg2 } else { "$agent-1" }
        Post-Event (@{ type = "subagent_start"; agent = $agent; agent_id = $id } | ConvertTo-Json -Compress)
    }
    "subagent_stop"  {
        $id = if ($Arg1) { $Arg1 } else { "Explore-1" }
        Post-Event (@{ type = "subagent_stop"; agent_id = $id } | ConvertTo-Json -Compress)
    }
    "close" {
        $id = if ($Arg1) { $Arg1 } else { "Explore-1" }
        Post-Event (@{ type = "close"; agent_id = $id } | ConvertTo-Json -Compress)
    }
    "close_subagents" { Post-Event '{"type":"close_subagents"}' }
    "close_all"       { Post-Event '{"type":"close_all"}' }
    "hide_main"       { Post-Event '{"type":"hide_main"}' }
    "show_main"       { Post-Event '{"type":"show_main"}' }
    "scale" {
        $s = if ($Arg1) { [double]$Arg1 } else { 1.0 }
        Post-Event (@{ type = "set_scale"; scale = $s } | ConvertTo-Json -Compress)
    }
    "say" {
        $t = if ($Arg1) { $Arg1 } else { "hello!" }
        Post-Event (@{ type = "say"; text = $t } | ConvertTo-Json -Compress)
    }
    "toggle_speech" { Post-Event '{"type":"toggle_speech"}' }
    "stats" {
        $stats = Invoke-RestMethod -Method Get -Uri "http://${HostName}:${Port}/stats"
        $stats | ConvertTo-Json -Depth 6
        return
    }
    "set_role" {
        $role = if ($Arg1) { $Arg1 } else { "main" }
        $chibi = $Arg2  # empty means "Default (auto)"
        Post-Event (@{ type = "set_role"; role = $role; chibi = $chibi } | ConvertTo-Json -Compress)
    }
    "play_anim" {
        $anim = if ($Arg1) { $Arg1 } else { "idle" }
        $text = $Arg2
        Post-Event (@{ type = "play_anim"; anim = $anim; text = $text } | ConvertTo-Json -Compress)
    }
    default { Write-Error "unknown command: $Command"; exit 2 }
}

"ok: $Command"
