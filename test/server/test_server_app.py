from unittest.mock import MagicMock, call

import flask
import pytest

from randovania.network_common.error import NotLoggedIn, ServerError, InvalidSession
from randovania.server import database
from randovania.server.multiplayer import session_common
from randovania.server.server_app import ServerApp, EnforceDiscordRole


@pytest.fixture(name="server_app")
def server_app_fixture(flask_app):
    pytest.importorskip("engineio.async_drivers.threading")

    flask_app.config['SECRET_KEY'] = "key"
    flask_app.config["DISCORD_CLIENT_ID"] = 1234
    flask_app.config["DISCORD_CLIENT_SECRET"] = 5678
    flask_app.config["DISCORD_REDIRECT_URI"] = "http://127.0.0.1:5000/callback/"
    flask_app.config["FERNET_KEY"] = b's2D-pjBIXqEqkbeRvkapeDn82MgZXLLQGZLTgqqZ--A='
    flask_app.config["GUEST_KEY"] = b's2D-pjBIXqEqkbeRvkapeDn82MgZXLLQGZLTgqqZ--A='
    flask_app.config["ENFORCE_ROLE"] = None
    server = ServerApp(flask_app)
    server.metrics.summary = MagicMock()
    server.metrics.summary.return_value.side_effect = lambda x: x
    return server


def test_session(server_app):
    server_app.sio = MagicMock()

    with server_app.app.test_request_context():
        flask.request.sid = 1234
        result = server_app.session()

    assert result == server_app.sio.server.session.return_value
    server_app.sio.server.session.assert_called_once_with(1234, namespace=None)


def test_get_session(server_app):
    server_app.sio = MagicMock()

    with server_app.app.test_request_context():
        flask.request.sid = 1234
        result = server_app.get_session()

    assert result == server_app.sio.server.get_session.return_value
    server_app.sio.server.get_session.assert_called_once_with(1234, namespace=None)


def test_get_current_user_ok(server_app, clean_database):
    server_app.get_session = MagicMock(return_value={"user-id": 1234})
    user = database.User.create(id=1234, name="Someone")

    # Run
    result = server_app.get_current_user()

    # Assert
    assert result == user


def test_get_current_user_not_logged(server_app, clean_database):
    server_app.get_session = MagicMock(return_value={})

    # Run
    with pytest.raises(NotLoggedIn):
        server_app.get_current_user()


def test_get_current_user_unknown_user(server_app, clean_database):
    server_app.get_session = MagicMock(return_value={"user-id": 1234})

    # Run
    with pytest.raises(InvalidSession):
        server_app.get_current_user()


def test_on_success_ok(server_app):
    # Setup
    custom = MagicMock(return_value={"foo": 12345})
    server_app.on("custom", custom)

    # Run
    test_client = server_app.sio.test_client(server_app.app)
    result = test_client.emit("custom", callback=True)

    # Assert
    custom.assert_called_once_with(server_app)
    assert result == {"result": {"foo": 12345}}


def test_on_success_network_error(server_app):
    # Setup
    error = NotLoggedIn()
    custom = MagicMock(side_effect=error)
    server_app.on("custom", custom)

    # Run
    test_client = server_app.sio.test_client(server_app.app)
    result = test_client.emit("custom", callback=True)

    # Assert
    custom.assert_called_once_with(server_app)
    assert result == error.as_json


def test_on_success_exception(server_app):
    # Setup
    custom = MagicMock(side_effect=RuntimeError("something happened"))
    server_app.on("custom", custom)

    # Run
    test_client = server_app.sio.test_client(server_app.app)
    result = test_client.emit("custom", callback=True)

    # Assert
    custom.assert_called_once_with(server_app)
    assert result == ServerError().as_json


@pytest.mark.parametrize("valid", [False, True])
def test_verify_user(mocker, valid):
    # Setup
    mock_session = mocker.patch("requests.Session")
    mock_session.return_value.headers = {}
    mock_session.return_value.get.return_value.json.return_value = {
        "roles": ["5678" if valid else "67689"]
    }

    # Run
    enforce = EnforceDiscordRole({
        "guild_id": 1234,
        "role_id": 5678,
        "token": "da_token",
    })
    result = enforce.verify_user(2345)

    # Assert
    assert result == valid
    mock_session.return_value.get.assert_called_once_with(
        "https://discordapp.com/api/guilds/1234/members/2345"
    )
    mock_session.return_value.get.return_value.json.assert_called_once_with()
    assert mock_session.return_value.headers == {
        "Authorization": "Bot da_token",
    }
