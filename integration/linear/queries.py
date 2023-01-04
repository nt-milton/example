def get_issue_query(issues_params: str, project: str) -> str:
    return (
        """
            {
                project(id: \""""
        + project
        + """\") {
                    issues"""
        + issues_params
        + """ {
                        nodes {
                            id
                            title
                            description
                            identifier
                            startedAt
                            url
                            project {
                                name
                            }
                            assignee {
                                name
                            }
                            creator {
                                name
                            }
                            state {
                                name
                            }
                        }
                        pageInfo {
                          hasNextPage
                          endCursor
                        }
                    }
                }
            }
            """
    )


projects_query = """
    {
      projects {
        nodes {
            id
            name
            description
        }
      }
    }
    """

users_query = """
   {
       users {
           nodes {
               id
               name
               displayName
               admin
               organization {
                   name
               }
               active
               email
           }
       }
   }"""


viewer_query = """
    {
      viewer {
        id
        name
        email
        admin
      }
    }
    """
