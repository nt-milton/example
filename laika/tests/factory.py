def mock_info_context_user(user):
    class MockContext:
        def __init__(self):
            self.user = user

    mc = MockContext()

    class MockInfo:
        def __init__(self, context):
            self.context = context

    return MockInfo(mc)
