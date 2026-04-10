from typing import Self

from paraview import servermanager
from trame.app.dataclass import StateDataModel, Sync, watch
from trame_dataclass.v2 import ServerOnly

from .pipeline import SourceProxy


class OperatorTreeNode(StateDataModel):
    title = Sync(str)
    children = Sync(list, list, has_dataclass=True)
    count = Sync(int)

    def update_count(self):
        local_count = 0
        for n in self.children:
            local_count += n.update_count()
        self.count = local_count
        return local_count


class OperatorNode(StateDataModel):
    title = Sync(str)
    name = Sync(str)
    tags = Sync(list[str], list)
    favorite = Sync(bool, False)
    icon = Sync(str)

    def update_count(self):
        return 1

    @watch("favorite")
    def _on_fav(self, favorite):
        self.server.controller.update_favorite_operator(self.name, favorite)


class Operator(StateDataModel):
    name = Sync(str)
    input = Sync(Self | SourceProxy, has_dataclass=True)
    config = Sync(dict, dict, client_deep_reactive=True)
    proxy = ServerOnly(servermanager.Proxy | None)
