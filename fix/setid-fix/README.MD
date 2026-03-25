# /setid Fix Archive

This folder groups the local fix records directly related to the `qq_official`
`/setid` workflow, stable host-side workspace entry, real-device test process,
and the follow-up timing/permission fixes.

Ordering rule:

- Files are sorted by the current filesystem timestamp of the original records.
- If two files share the same timestamp, they are ordered by filename.

Chronology:

- `01_qq_official_private_workspace_persistence.md`
- `02_qq_official_private_workspace_persistence_decisions.md`
- `03_qq_official_workspace_host_permissions_fix.md`
- `04_qq_official_first_c2c_setid_short_circuit_fix.md`
- `05_qq_official_pre_setid_dialog_guard_fix.md`
- `06_测试.md`
- `07_qq_official_first_shipyard_binding_timing_fix.md`
- `08_qq_official_workspace_host_other_write_fix.md`
- `09_qq_official_setid_prompt_state_and_cleanup_fix.md`

Current test status from the latest real-device run:

- first C2C prompt works
- `/setid tca001` registers successfully
- first sandbox request resolves the stable `workspace` symlink
- host-side write/read through the stable entry works without `sudo`
- repeated `/setid tca001` is idempotent
- restart keeps the same workspace binding and file contents
