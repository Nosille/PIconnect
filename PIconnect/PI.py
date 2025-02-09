""" PI
    Core containers for connections to PI databases
"""
import warnings
from typing import Any, Dict, List, Optional, Union, cast

import PIconnect._typing.Generic as _dotNetGeneric
import PIconnect.PIPoint as PIPoint_
from PIconnect import AF, PIConsts
from PIconnect._utils import InitialisationWarning

__all__ = ["PIServer", "PIPoint"]

PIPoint = PIPoint_.PIPoint


def _lookup_servers() -> Dict[str, AF.PI.PIServer]:
    servers: Dict[str, AF.PI.PIServer] = {}
    from System import Exception as dotNetException  # type: ignore

    for server in AF.PI.PIServers():
        try:
            servers[server.Name] = server
        except (Exception, dotNetException) as e:  # type: ignore
            warnings.warn(
                f"Failed loading server data for {server.Name} "
                f"with error {type(cast(Exception, e)).__qualname__}",
                InitialisationWarning,
            )
    return servers


def _lookup_default_server() -> Optional[AF.PI.PIServer]:

    default_server = None
    try:
        default_server = AF.PI.PIServers().DefaultPIServer
    except Exception:
        warnings.warn("Could not load the default PI Server", ResourceWarning)
    return default_server


class PIServer(object):  # pylint: disable=useless-object-inheritance
    """PIServer is a connection to an OSIsoft PI Server

    Args:
        server (str, optional): Name of the server to connect to, defaults to None
        username (str, optional): can be used only with password as well
        password (str, optional): -//-
        todo: domain, auth
        timeout (int, optional): the maximum seconds an operation can take

    .. note::
        If the specified `server` is unknown a warning is thrown and the connection
        is redirected to the default server, as if no server was passed. The list
        of known servers is available in the `PIServer.servers` dictionary.
    """

    version = "0.2.2"

    #: Dictionary of known servers, as reported by the SDK
    servers = _lookup_servers()
    #: Default server, as reported by the SDK
    default_server = _lookup_default_server()

    def __init__(
        self,
        server: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        domain: Optional[str] = None,
        authentication_mode: PIConsts.AuthenticationMode = PIConsts.AuthenticationMode.WINDOWS_AUTHENTICATION,
        timeout: Optional[int] = None,
    ) -> None:
        if server is None:
            if self.default_server is None:
                raise ValueError(
                    "No server was specified and no default server was found."
                )
            self.connection = self.default_server
        elif server not in self.servers:
            if self.default_server is None:
                raise ValueError(
                    f"Server '{server}' not found and no default server was found."
                )
            message = 'Server "{server}" not found, using the default server.'
            warnings.warn(message=message.format(server=server), category=UserWarning)
            self.connection = self.default_server
        else:
            self.connection = self.servers[server]

        if bool(username) != bool(password):
            raise ValueError(
                "When passing credentials both the username and password must be specified."
            )
        if domain and not username:
            raise ValueError(
                "A domain can only specified together with a username and password."
            )
        if username:
            from System.Net import NetworkCredential  # type: ignore
            from System.Security import SecureString  # type: ignore

            secure_pass = cast(_dotNetGeneric.SecureString, SecureString())
            if password is not None:
                for c in password:
                    secure_pass.AppendChar(c)
            cred = [username, secure_pass] + ([domain] if domain else [])
            self._credentials = (
                cast(_dotNetGeneric.NetworkCredential, NetworkCredential(*cred)),
                AF.PI.PIAuthenticationMode(int(authentication_mode)),
            )
        else:
            self._credentials = None

        if timeout:
            from System import TimeSpan  # type: ignore

            # System.TimeSpan(hours, minutes, seconds)
            self.connection.ConnectionInfo.OperationTimeOut = cast(
                _dotNetGeneric.TimeSpan, TimeSpan(0, 0, timeout)
            )

    def __enter__(self):
        if self._credentials:
            self.connection.Connect(*self._credentials)
        else:
            # Don't force to retry connecting if previous attempt failed
            force_connection = False
            self.connection.Connect(force_connection)
        return self

    def __exit__(self, *args: Any):
        print("disconnecting from Pi Data Server")
        self.connection.Disconnect()

    def __repr__(self) -> str:
        return "%s(\\\\%s)" % (self.__class__.__name__, self.server_name)

    @property
    def server_name(self):
        """server_name

        Name of the connected server
        """
        return self.connection.Name

    def search(
        self, query: Union[str, List[str]], source: Optional[str] = None
    ) -> List[PIPoint_.PIPoint]:
        """search

        Search PIPoints on the PIServer

        Args:
            query (str or [str]): String or list of strings with queries
            source (str, optional): Defaults to None. Point source to limit the results

        Returns:
            list: A list of :class:`PIPoint` objects as a result of the query

        .. todo::

            Reject searches while not connected
        """
        if isinstance(query, list):
            return [y for x in query for y in self.search(x, source)]
        # elif not isinstance(query, str):
        #     raise TypeError('Argument query must be either a string or a list of strings,' +
        #                     'got type ' + str(type(query)))
        return [
            PIPoint_.PIPoint(pi_point)
            for pi_point in AF.PI.PIPoint.FindPIPoints(
                self.connection, str(query), source, None
            )
        ]
