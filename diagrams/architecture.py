from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.gitops import ArgoCD
from diagrams.k8s.compute import Deploy
from diagrams.k8s.others import CRD

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.8",
    "ranksep": "1.6",
    "nodesep": "1.0",
    "splines": "ortho",
}

HUB = {"bgcolor": "#FDECEA", "style": "rounded", "pencolor": "#CC0000", "penwidth": "2"}
OCP = {"bgcolor": "#FFF3E0", "style": "rounded", "pencolor": "#CC0000", "penwidth": "1.5"}
K8S = {"bgcolor": "#E3F2FD", "style": "rounded", "pencolor": "#1565C0", "penwidth": "1.5"}
MCS = {"style": "dashed", "pencolor": "#888888", "fontsize": "12"}

with Diagram(
    "ACM Pull Model — High-Level Architecture",
    filename="diagrams/out/architecture",
    show=False,
    direction="TB",
    outformat="png",
    graph_attr=graph_attr,
):
    with Cluster("Hub — OpenShift (ACM 2.17 + GitOps 1.21)", graph_attr=HUB):
        principal = ArgoCD("Agent\nPrincipal")
        policies = CRD("ACM\nPolicies")

    with Cluster("MCS: mortgage", graph_attr=MCS):
        with Cluster("insolvency-check-sno\nOCP  |  platform=ocp", graph_attr=OCP):
            agent_ins = ArgoCD("Agent")
        with Cluster("kind-local\nKubernetes  |  platform=generic", graph_attr=K8S):
            agent_kind = ArgoCD("Agent")

    with Cluster("MCS: insurance", graph_attr=MCS):
        with Cluster("parasol-sno\nOCP  |  platform=ocp", graph_attr=OCP):
            agent_par = ArgoCD("Agent")

    agent_ins >> Edge(color="darkgreen", style="dashed") >> principal
    agent_kind >> Edge(color="darkgreen", style="dashed") >> principal
    agent_par >> Edge(color="darkgreen", style="dashed") >> principal
