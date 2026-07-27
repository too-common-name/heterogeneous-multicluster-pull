from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.rbac import Group, ClusterRole
from diagrams.k8s.group import NS

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.8",
    "ranksep": "1.6",
    "nodesep": "1.0",
}

with Diagram(
    "Hub RBAC Model",
    filename="diagrams/out/rbac_model",
    show=False,
    direction="LR",
    outformat="png",
    graph_attr=graph_attr,
):
    with Cluster("Groups"):
        foundation = Group("foundation-\nadmins")
        mortgage_grp = Group("mortgage-\nteam")
        insurance_grp = Group("insurance-\nteam")

    ca = ClusterRole("cluster-admin")

    with Cluster("Mortgage"):
        ns_mortgage = NS("mortgage-\ngitops")
        ns_ins = NS("insolvency-\ncheck-sno")
        ns_kind = NS("kind-local")

    with Cluster("Insurance"):
        ns_insurance = NS("insurance-\ngitops")
        ns_par = NS("parasol-sno")

    foundation >> Edge(style="bold", color="black") >> ca
    mortgage_grp >> Edge(style="bold", color="black") >> ns_mortgage
    insurance_grp >> Edge(style="bold", color="black") >> ns_insurance
    mortgage_grp >> Edge(style="dashed", color="gray") >> ns_ins
    mortgage_grp >> Edge(style="dashed", color="gray") >> ns_kind
    insurance_grp >> Edge(style="dashed", color="gray") >> ns_par
