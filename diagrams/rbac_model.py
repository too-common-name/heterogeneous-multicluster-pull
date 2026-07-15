from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.rbac import Group, ClusterRole
from diagrams.k8s.group import NS

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
    "ranksep": "1.2",
    "nodesep": "0.8",
}

ADMIN = {"color": "black", "style": "bold", "penwidth": "2.0"}
READ_ONLY = {"color": "gray", "style": "dashed"}

with Diagram(
    "Hub RBAC Model",
    filename="diagrams/out/rbac_model",
    show=False,
    direction="LR",
    outformat="png",
    graph_attr=graph_attr,
):

    with Cluster("Groups"):
        foundation = Group("foundation-admins")
        mortgage_grp = Group("mortgage-team")
        insurance_grp = Group("insurance-team")

    ca = ClusterRole("cluster-admin")

    with Cluster("Mortgage scope"):
        ns_mortgage = NS("mortgage-gitops")
        ns_ins_sno = NS("insolvency-check-sno")
        ns_kind = NS("kind-local")

    with Cluster("Insurance scope"):
        ns_insurance = NS("insurance-gitops")
        ns_par = NS("parasol-sno")

    # ── solid = admin ──
    foundation >> Edge(label="cluster-admin", **ADMIN) >> ca
    mortgage_grp >> Edge(label="admin", **ADMIN) >> ns_mortgage
    insurance_grp >> Edge(label="admin", **ADMIN) >> ns_insurance

    # ── dashed = view + secret-reader (read-only) ──
    mortgage_grp >> Edge(label="view + secret-reader", **READ_ONLY) >> ns_ins_sno
    mortgage_grp >> Edge(label="view + secret-reader", **READ_ONLY) >> ns_kind
    insurance_grp >> Edge(label="view + secret-reader", **READ_ONLY) >> ns_par
