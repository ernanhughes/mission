-- Enable the Writer Editing integration for installations created before the
-- adapter existed. The Writer CLI remains optional: if the executable is
-- missing the adapter reports unavailable instead of inventing reports.
UPDATE applications
SET integration_adapter = 'writer',
    adapter_enabled = 1,
    adapter_config = json_object(
        'executable', 'C:\Projects\writer\venv\Scripts\writer.exe',
        'working_directory', 'C:\Projects\writer',
        'arguments', json_array('editing', 'summary', '--json'),
        'timeout_seconds', 60,
        'env_names', json_array('WRITER_PROJECTS_CONFIG')
    )
WHERE id = 'writer'
  AND (integration_adapter IS NULL OR integration_adapter = '');
