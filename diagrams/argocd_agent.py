from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.gitops import ArgoCD
from diagrams.k8s.rbac import Group
from diagrams.k8s.infra import Node

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.8",
    "ranksep": "1.4",
    "nodesep": "0.4",
}

NS_STYLE = {"bgcolor": "#F5F5F5", "style": "rounded", "pencolor": "#999999"}
PROJ_F = {"bgcolor": "#FDECEA", "style": "rounded", "pencolor": "#CC0000", "penwidth": "2"}
PROJ_M = {"bgcolor": "#E8F5E9", "style": "rounded", "pencolor": "#388E3C", "penwidth": "2"}
PROJ_I = {"bgcolor": "#E3F2FD", "style": "rounded", "pencolor": "#1565C0", "penwidth": "2"}

with Diagram(
    "ArgoCD Multi-Tenant Model",
    filename="diagrams/out/argocd_agent",
    show=False,
    direction="TB",
    outformat="png",
    graph_attr=graph_attr,
):
    # --- Column 1: Mortgage ---
    mort_user = Group("mortgage-team")

    with Cluster("mortgage-gitops", graph_attr=NS_STYLE):
        with Cluster("mortgage Project\ndst: insolvency, kind", graph_attr=PROJ_M):
            app_mort = ArgoCD("team apps")

    cl_ins = Node("insolvency-\ncheck-sno")
    cl_kind = Node("kind-local")

    # --- Column 2: Foundation ---
    found_user = Group("foundation-admin")

    with Cluster("openshift-gitops", graph_attr=NS_STYLE):
        with Cluster("foundation Project\ndst: */*  (all clusters)", graph_attr=PROJ_F):
            app_boot = ArgoCD("bootstrap")
            appset_ocp = ArgoCD("OCP AppSet")
            appset_gen = ArgoCD("Generic AppSet")

    # --- Column 3: Insurance ---
    ins_user = Group("insurance-team")

    with Cluster("insurance-gitops", graph_attr=NS_STYLE):
        with Cluster("insurance Project\ndst: parasol", graph_attr=PROJ_I):
            app_ins = ArgoCD("team apps")

    cl_par = Node("parasol-sno")

    # Team → project
    mort_user >> Edge(color="#388E3C", style="dashed") >> app_mort
    found_user >> Edge(color="#CC0000", style="dashed") >> app_boot
    ins_user >> Edge(color="#1565C0", style="dashed") >> app_ins

    # Mortgage → its clusters
    app_mort >> Edge(color="#388E3C") >> cl_ins
    app_mort >> Edge(color="#388E3C") >> cl_kind

    # Insurance → its cluster
    app_ins >> Edge(color="#1565C0") >> cl_par
