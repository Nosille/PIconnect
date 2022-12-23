""" PIAF
    Core containers for connections to the PI Asset Framework.
"""
import dataclasses
import warnings
from typing import Any, Dict, Optional, Union, cast

import PIconnect._typing.Generic as _dotNetGeneric
from PIconnect import AF, PIAFBase, PIConsts, _time
from PIconnect._utils import InitialisationWarning


@dataclasses.dataclass(frozen=True)
class PIAFServer:
    server: AF.PISystem
    databases: Dict[str, AF.AFDatabase] = dataclasses.field(default_factory=dict)

    def __getitem__(self, attr: str) -> Union[AF.PISystem, Dict[str, AF.AFDatabase]]:
        return getattr(self, attr)


ServerSpec = Dict[str, Union[AF.PISystem, Dict[str, AF.AFDatabase]]]


def _lookup_servers() -> Dict[str, ServerSpec]:
    from System import Exception as dotNetException  # type: ignore

    servers: Dict[str, PIAFServer] = {}
    for s in AF.PISystems():
        try:
            servers[s.Name] = server = PIAFServer(s)
        except (Exception, dotNetException) as e:  # type: ignore
            warnings.warn(
                f"Failed loading server data for {s.Name} "
                f"with error {type(cast(Exception, e)).__qualname__}",
                InitialisationWarning,
            )
    return {
        server_name: {
            "server": server.server
        }
        for server_name, server in servers.items()
    }


def _lookup_default_server() -> Optional[ServerSpec]:
    servers = _lookup_servers()
    if AF.PISystems().DefaultPISystem:
        return servers[AF.PISystems().DefaultPISystem.Name]
    elif len(servers) > 0:
        return servers[list(_lookup_servers())[0]]
    else:
        return None


class PIAFDatabase(object):
    """PIAFDatabase

    Context manager for connections to the PI Asset Framework database.
    """

    version = "0.2.0"

    # print("Find Available AF Servers")
    servers: Dict[str, ServerSpec] = _lookup_servers()
    # for s in AF.PISystems():
    #     print("    " + str(s.Name))
    # print("lookup default server")
    default_server: Optional[ServerSpec] = _lookup_default_server()
    # print("found default server")

    def __init__(
        self, 
        server: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        domain: Optional[str] = None,
        authentication_mode: PIConsts.AuthenticationMode = PIConsts.AuthenticationMode.WINDOWS_AUTHENTICATION,
        timeout: Optional[int] = None, 
        database: Optional[str] = None
    ) -> None:

        # print("Setup credentials")
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
            )
        else:
            self._credentials = None
        
        # print("initialize server")
        server_spec = self._initialise_server(server)
        self.server: AF.PISystem = server_spec["server"]  # type: ignore
        # print("PISystem:" + str(self.server.Name))
        self.database: AF.AFDatabase = self._initialise_database(database)

    def _initialise_server(self, server: Optional[str]) -> ServerSpec:
        if server is None:
            if self.default_server is None:
                raise ValueError("No server specified and no default server found.")
            return self.default_server

        if server not in self.servers:
            if self.default_server is None:
                raise ValueError(
                    f'Server "{server}" not found and no default server found.'
                )
            message = 'Server "{server}" not found, using the default server.'
            warnings.warn(message=message.format(server=server), category=UserWarning)
            return self.default_server

        return self.servers[server]

    def _initialise_database(
        self, database: Optional[str]
    ) -> AF.AFDatabase:
        self.server.Connect(*self._credentials)
        default_db = self.server.Databases.DefaultDatabase
        # print("Default Database:" + str(default_db.Name))
        if database is None:
            return default_db


        return self.server.Databases[database]

    def __enter__(self) -> "PIAFDatabase":
        # if self._credentials:
        #     self.server.Connect(*self._credentials)
        # else:    
        #     self.server.Connect()

        return self

    def __exit__(self, *args: Any) -> None:
        pass
        print("disconnecting from Pi AF Server")
        # Disabled disconnecting because garbage collection sometimes impedes
        # connecting to another server later
        # self.server.Disconnect()

    def __repr__(self) -> str:
        return "%s(\\\\%s\\%s)" % (
            self.__class__.__name__,
            self.server_name,
            self.database_name,
        )

    @property
    def server_name(self) -> str:
        """Return the name of the connected PI AF server."""
        return self.server.Name

    @property
    def database_name(self) -> str:
        """Return the name of the connected PI AF database."""
        return self.database.Name

    @property
    def children(self) -> Dict[str, "PIAFElement"]:
        """Return a dictionary of the direct child elements of the database."""
        return {c.Name: PIAFElement(c) for c in self.database.Elements}

    def descendant(self, path: str) -> "PIAFElement":
        """Return a descendant of the database from an exact path."""
        return PIAFElement(self.database.Elements.get_Item(path))

    def event_frames(
        self,
        start_time: _time.TimeLike = "",
        start_index: int = 0,
        max_count: int = 1000,
        search_mode: PIConsts.EventFrameSearchMode = PIConsts.EventFrameSearchMode.STARTING_AFTER,
        search_full_hierarchy: bool = False,
    ) -> Dict[str, "PIAFEventFrame"]:
        _start_time = _time.to_af_time(start_time)
        _search_mode = AF.EventFrame.AFEventFrameSearchMode(int(search_mode))
        return {
            frame.Name: PIAFEventFrame(frame)
            for frame in AF.EventFrame.AFEventFrame.FindEventFrames(
                self.database,
                None,
                _start_time,
                start_index,
                max_count,
                _search_mode,
                None,
                None,
                None,
                None,
                search_full_hierarchy,
            )
        }


class PIAFElement(PIAFBase.PIAFBaseElement[AF.Asset.AFElement]):
    """Container for PI AF elements in the database."""

    version = "0.1.0"

    @property
    def parent(self) -> Optional["PIAFElement"]:
        """Return the parent element of the current element, or None if it has none."""
        if not self.element.Parent:
            return None
        return self.__class__(self.element.Parent)

    @property
    def children(self) -> Dict[str, "PIAFElement"]:
        """Return a dictionary of the direct child elements of the current element."""
        return {c.Name: self.__class__(c) for c in self.element.Elements}

    def descendant(self, path: str) -> "PIAFElement":
        """Return a descendant of the current element from an exact path."""
        return self.__class__(self.element.Elements.get_Item(path))


class PIAFEventFrame(PIAFBase.PIAFBaseElement[AF.EventFrame.AFEventFrame]):
    """Container for PI AF Event Frames in the database."""

    version = "0.1.0"

    @property
    def event_frame(self) -> AF.EventFrame.AFEventFrame:
        return self.element

    @property
    def parent(self) -> Optional["PIAFEventFrame"]:
        """Return the parent element of the current event frame, or None if it has none."""
        if not self.element.Parent:
            return None
        return self.__class__(self.element.Parent)

    @property
    def children(self) -> Dict[str, "PIAFEventFrame"]:
        """Return a dictionary of the direct child event frames of the current event frame."""
        return {c.Name: self.__class__(c) for c in self.element.EventFrames}
