from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.gitops import ArgoCD

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
    "ranksep": "1.0",
    "nodesep": "0.6",
}

OCP_STYLE = {"bgcolor": "#FDECEA", "style": "rounded", "pencolor": "#EE0000", "penwidth": "2"}
K8S_STYLE = {"bgcolor": "#E8F0FE", "style": "rounded", "pencolor": "#326CE5", "penwidth": "2"}
MCS_STYLE = {"style": "dashed", "pencolor": "#666666"}

with Diagram(
    "ACM Pull Model — ArgoCD Agent Architecture",
    filename="diagrams/out/architecture",
    show=False,
    direction="TB",
    outformat="png",
    graph_attr=graph_attr,
):

    with Cluster("Hub Cluster\nOpenShift (ACM 2.17 + GitOps 1.21)", graph_attr=OCP_STYLE):
        principal = ArgoCD("Agent Principal")

    with Cluster("ManagedClusterSet: mortgage", graph_attr=MCS_STYLE):

        with Cluster("insolvency-check-sno\n[OpenShift] team=mortgage", graph_attr=OCP_STYLE):
            agent_ins = ArgoCD("ArgoCD Agent")

        with Cluster("kind-local\n[Kubernetes] team=mortgage", graph_attr=K8S_STYLE):
            agent_kind = ArgoCD("ArgoCD Agent")

    with Cluster("ManagedClusterSet: insurance", graph_attr=MCS_STYLE):

        with Cluster("parasol-sno\n[OpenShift] team=insurance", graph_attr=OCP_STYLE):
            agent_par = ArgoCD("ArgoCD Agent")

    agent_ins >> Edge(label="mTLS pull", style="dashed", color="darkgreen") >> principal
    agent_kind >> Edge(label="mTLS pull", style="dashed", color="darkgreen") >> principal
    agent_par >> Edge(label="mTLS pull", style="dashed", color="darkgreen") >> principal
    principal >> Edge(label="blocked", style="dotted", color="red") >> [agent_ins, agent_par]
