-- playlist_recorder: switch to (or open) the recorder project tab.
local path = [[{project_path}]]
local i = 0
while true do
  local proj, fn = reaper.EnumProjects(i)
  if not proj then break end
  if fn:lower() == path:lower() then
    reaper.SelectProjectInstance(proj)
    return
  end
  i = i + 1
end
reaper.Main_OnCommand(40859, 0) -- New project tab
reaper.Main_openProject("noprompt:" .. path)
