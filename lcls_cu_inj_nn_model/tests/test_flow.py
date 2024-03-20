from lcls_cu_inj_nn_model.flow import flow, output_variables


def test_flow_execution():
    # mark success on success of evaluate task
    flow.set_reference_tasks([output_variables])

    # Running without passing parameters require defaults for all parameters
    flow_run = flow.run()

    # check success of flow
    assert flow_run.is_successful()
