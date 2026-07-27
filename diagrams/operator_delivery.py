from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.gitops import ArgoCD
from diagrams.onprem.vcs import Git
from diagrams.k8s.compute import Deploy
from diagrams.k8s.others import CRD
from diagrams.k8s.infra import Node

graph_attr = {
    "fontsize": "13",
    "bgcolor": "white",
    "pad": "0.8",
    "ranksep": "1.2",
    "nodesep": "0.8",
}

HUB = {"bgcolor": "#F3E5F5", "style": "rounded", "pencolor": "#7B1FA2", "penwidth": "1.5"}
OCP = {"bgcolor": "#FDECEA", "style": "rounded", "pencolor": "#CC0000", "penwidth": "1.5"}
K8S = {"bgcolor": "#E3F2FD", "style": "rounded", "pencolor": "#1565C0", "penwidth": "1.5"}

with Diagram(
    "Operator Delivery — OCP vs Generic",
    filename="diagrams/out/operator_delivery",
    show=False,
    direction="TB",
    outformat="png",
    graph_attr=graph_attr,
):
    git = Git("Git repo")

    with Cluster("Hub", graph_attr=HUB):
        appset_ocp = ArgoCD("AppSet\nOCP operators")
        appset_gen = ArgoCD("AppSet\nGeneric operators")
        policy = CRD("ACM Policies\n(OperatorPolicy\n+ ConfigPolicy)")
        principal = ArgoCD("Agent\nPrincipal")

    with Cluster("OCP spoke", graph_attr=OCP):
        cfg_ctrl = Deploy("config-policy-\ncontroller")
        olm = CRD("OLM")
        op_ocp = Deploy("Loki Operator")

    with Cluster("Generic spoke", graph_attr=K8S):
        agent = ArgoCD("Agent")
        op_gen = Deploy("Loki (Helm)")

    # OCP path: Git → AppSet → Policies → config-policy-controller → OLM → Operator
    git >> Edge(color="#7B1FA2") >> appset_ocp
    appset_ocp >> Edge(color="#7B1FA2") >> policy
    cfg_ctrl >> Edge(color="#CC0000", style="bold") >> policy
    cfg_ctrl >> Edge(color="#CC0000") >> olm
    olm >> Edge(color="#CC0000") >> op_ocp

    # Generic path: Git → AppSet → Principal ← Agent pulls → Operator
    git >> Edge(color="#1565C0") >> appset_gen
    appset_gen >> Edge(color="#1565C0") >> principal
    agent >> Edge(color="darkgreen", style="dashed") >> principal
    agent >> Edge(color="#1565C0") >> op_gen
