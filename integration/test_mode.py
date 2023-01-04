from typing import Union


class TestConnectionAccount:
    in_test_mode = False
    connection_id: Union[int, None] = None
    responses: list = []

    def init(self, connection_account_id: int):
        self.connection_id = connection_account_id
        self.responses = []
        self.in_test_mode = True

    def reset_test_mode(self, connection_account_id: int):
        if self.connection_id == connection_account_id and self.in_test_mode:
            self.connection_id = None
            self.responses = []
            self.in_test_mode = False

    def save_raw_data_in_test_mode(self, connection_account_id: int, data: str) -> None:
        if self.connection_id == connection_account_id and self.in_test_mode:
            self.responses.append(data)


test_state = TestConnectionAccount()


def is_connection_on_test_mode(connection_account_id: int) -> bool:
    return test_state.connection_id == connection_account_id and test_state.in_test_mode
