from platform_mcp import delivery

DONE = {"status": "success", "url": "http://localhost:3000/platform/loyalty-points/actions/runs/2"}
SYNCED = {"sync": "Synced", "health": "Healthy", "message": None}
APP = {"image": "registry/services:loyalty-points-abc", "ready": True}


def state(run=DONE, argo=SYNCED, app=APP, pods=()):
    return delivery.summarize("loyalty-points", "checkout-dev", run, argo, app, list(pods))


def test_follows_the_delivery_in_order():
    assert state(run={"status": "running"})[0] == "building"
    assert state(run={"status": "none"})[0] == "building"
    assert state(app=None)[0] == "deploying"
    assert state(app={"image": "", "ready": True})[0] == "deploying"
    assert state(app={**APP, "ready": False})[0] == "starting"


def test_points_to_the_failed_pipeline_run():
    s, next_step = state(run={**DONE, "status": "failure"})
    assert s == "pipeline_failed" and DONE["url"] in next_step


def test_reports_a_service_that_does_not_start():
    pod = {"ready": False, "restarts": 3, "waiting_reason": "CrashLoopBackOff", "logs": "Connection refused"}
    s, next_step = state(app={**APP, "ready": False}, pods=[pod])
    assert s == "failing" and "CrashLoopBackOff" in next_step and "logs" in next_step


def test_says_how_to_try_a_ready_service():
    s, next_step = state()
    assert s == "ready"
    assert "kubectl -n env-checkout-dev port-forward svc/loyalty-points 8080:80" in next_step
