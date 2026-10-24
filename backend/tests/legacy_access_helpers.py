from agent_keys import KeyCreate
from test_product import add_customer, PASSWORD

def key(client, **overrides):
    user=client.get("/api/auth/me").json()
    return client.app.state.hub.agent_keys.create(user, KeyCreate(**{"name":"Historical access test", "scopes":["search_policy"],"password":PASSWORD,"pseudonymize":False,**overrides}))

def case(client, reference="CASE-CUSTOMER", **overrides):
    customer = add_customer(client, reference, **overrides)
    response = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Seeded toolkit case",
            "description": "Investigate a synthetic customer for toolkit acceptance.",
        },
    )
    assert response.status_code == 201, response.text
    return customer, response.json()
