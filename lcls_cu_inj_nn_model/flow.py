import json
import k2eg
import math
import os
import torch

from lume_model.models import TorchModule
from prefect import flow, get_run_logger, task
from typing import Any, Dict


flow_dir = os.path.dirname(os.path.abspath(__file__))


@task()
def read_input_data(k2eg_client: k2eg.dml) -> Dict[str, float]:
    """ Read the input data our model expects from live PV values """
    pv_names = json.load(open(os.path.join(flow_dir, 'info/pv_mapping.json')))['pv_name_to_sim_name']
    input_parameter_values = {'CAMR:IN20:186:R_DIST': None, 'Pulse_length': 1.8550514181818183}

    for pv_name in pv_names.keys():
        if pv_name not in input_parameter_values and 'OTRS' not in pv_name and ':' in pv_name:
            input_parameter_values[pv_name] = None

    k2eg_pvs_to_monitor = ['ca://' + pv for pv in input_parameter_values.keys() if
                           pv not in ['CAMR:IN20:186:R_DIST', 'Pulse_length']]

    for pv_name in k2eg_pvs_to_monitor:
        input_parameter_values[pv_name.replace('ca://', '')] = k2eg_client.get(pv_name, 5.0)["value"]

    in_xrms_value = k2eg_client.get('ca://CAMR:IN20:186:XRMS')["value"]
    in_yrms_value = k2eg_client.get('ca://CAMR:IN20:186:YRMS')["value"]
    rdist = math.sqrt(in_xrms_value ** 2 + in_yrms_value ** 2)
    input_parameter_values['CAMR:IN20:186:R_DIST'] = rdist

    return input_parameter_values


@task()
def evaluate(lume_module: TorchModule, input_values: torch.Tensor) -> torch.Tensor:
    """ Run the trained model on the live data we retrieved """
    with torch.no_grad():
        predictions = lume_module(input_values)

    return predictions


@task()
def write_output(k2eg_client: k2eg.dml, predictions: torch.Tensor) -> None:
    """ Write the results of our predictions back to the relevant EPICS PVs """
    k2eg_client.put('pva://LUME:OTRS:IN20:571:XRMS', predictions[0].item(), 5.0)
    k2eg_client.put('pva://LUME:OTRS:IN20:571:YRMS', predictions[1].item(), 5.0)


@flow(name="lcls_cu_inj_nn_model_flow")
def lcls_cu_inj_nn_model_flow():
    logger = get_run_logger()
    logger.info(f'Starting flow run from: {flow_dir}')

    logger.info(f'Results for torch.cuda.is_available(): {torch.cuda.is_available()}')

    # Load the model we will run
    lume_module = TorchModule(os.path.join(flow_dir, "model/pv_module.yml"))
    logger.info(lume_module)

    # Read in PV data for our inputs
    os.environ['K2EG_PYTHON_CONFIGURATION_PATH_FOLDER'] = os.path.join(flow_dir, "k2eg")
    k2eg_client = k2eg.dml('env', 'app-test-3')
    input_parameter_values = read_input_data(k2eg_client)
    input_values = torch.tensor(list(input_parameter_values.values())).unsqueeze(0)

    logger.info(f'Obtained live values from EPICS are as follows: {input_parameter_values}')
    logger.info(f'Thus the input values to our model are: {input_values}')

    predictions = evaluate(lume_module, input_values)

    logger.info(f'Predictions: {predictions}')
    logger.info(predictions)

    # Write the output back to EPICS
    write_output(k2eg_client, predictions)

    k2eg_client.close()


def get_flow():
    return flow
