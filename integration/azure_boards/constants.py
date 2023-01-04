AZURE_BOARDS_SYSTEM = 'Azure Boards'
WORK_ITEMS_QUERY = (
    "SELECT [System.Id] FROM workitem WHERE [System.TeamProject] = '{project}'"
)
WORK_ITEMS_PER_REQUEST = 200
