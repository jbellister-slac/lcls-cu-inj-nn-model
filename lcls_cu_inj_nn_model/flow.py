from typing import Dict

from prefect import flow, get_run_logger, task

from lume_services.results import Result
from lume_services.tasks import (
    configure_lume_services,
    prepare_lume_model_variables,
    check_local_execution,
    SaveDBResult,
    LoadDBResult,
    LoadFile,
    SaveFile,
)
from lume_services.files import TextFile
from lume_model.variables import InputVariable, OutputVariable

from lcls_cu_inj_nn_model.model import LCLSCuInjNNModel
from lcls_cu_inj_nn_model import INPUT_VARIABLES


@task()
def preprocessing_task(input_variables, misc_settings):
    """If additional preprocessing of input variables are required, process the
    variables here. This task is flexible and can absorb other misc settings passed
    as parameters to the flow.

    Examples:
        Suppose we have a preprocessing step where we want to scale all values by some
        multiplier. This task would look like:

        ```python

        def preprocessing_task(input_variables, multiplier):
            for var_name in input_variables.keys():
                input_variables[var_name].value = input_variables[var_name].value
                                                        * multiplier

        ```

    """
    raise NotImplementedError("Called not implemented preprocessing_task in flow.")


@task()
def format_file(output_variables):
    """Task used for organizing an file object. The formatted object must be
    serializable by the file_type passed in the SaveFile task call.
    See https://slaclab.github.io/lume-services/services/files/ for more information
    about interacting with file objects and file systems

    Examples:
        Suppose we have a workflow with two results `text1` and `text2`. We'd like to
        concatenate the text and save in a text file. This would look like:
        ```python

        @task()
        def format_file(output_variables):
            text = output_variables["text1"].value + output_variables["text2"].value
            return text

        save_file_task = SaveFile()

        with Flow("my-flow") as flow:

            ... # set up params, evaluate, etc.

            output_variables = evaluate(formatted_input_variables)
            text = format_file(output_variables)

            file_parameters = save_file_task.parameters

            # save file
            my_file = save_file_task(
                text,
                filename = file_parameters["filename"],
                filesystem_identifier = file_parameters["filesystem_identifier"],
                file_type = TextFile # THIS MUST BE PASSED IN THE TASK CALL
            )

        ```

    """
    raise NotImplementedError("Called not implemented format_file in flow.")


@task()
def format_result(
    input_variables: Dict[str, InputVariable],
    output_variables: Dict[str, OutputVariable],
):
    """Formats model results into a LUME-services Result object. This task should be
    modified for custom organization of outputs.

    NOTE: Here we use the generic Result class defined in LUME-services https://slaclab.github.io/lume-services/api/results/
    Other Result types can be easily configured by subclassing this Result class and
    LUME-services pre-packages a result for Impact simulations: https://slaclab.github.io/lume-services/api/results/#lume_services.results.impact


    Args:
        input_variables (Dict[str, InputVariable]): Dictionary mapping input variable
            name to LUME-model variable.
        output_variables (Dict[str, OutputVariable]): Dictionary mapping output variable
            name to LUME-model variable.

    Returns:
        Result: Lume-Services Result object.

    """  # noqa

    inputs = {var_name: var.value for var_name, var in input_variables.items()}
    outputs = {var_name: var.value for var_name, var in output_variables.items()}

    return Result(inputs=inputs, outputs=outputs)


@task()
def load_input(var_name, parameter):
    # Confirm Inputs are Correctly Loaded!
    logger = get_run_logger()
    if parameter.value is None:
        parameter.value = parameter.default
    logger.info(f'Loaded {var_name} with value {parameter}')
    return parameter


@task()
def evaluate(formatted_input_vars, settings=None):

    if settings is None:
        settings = {}

    model = LCLSCuInjNNModel(**settings)

    return model.evaluate(formatted_input_vars)


# DEFINE TASK FOR SAVING DB RESULT
# See docs: https://slaclab.github.io/lume-services/api/tasks/#lume_services.tasks.db.SaveDBResult
save_db_result_task = SaveDBResult(timeout=30)

# DEFINE TASK FOR SAVING FILE
# See docs: https://slaclab.github.io/lume-services/api/tasks/#lume_services.tasks.file.SaveFile
save_file_task = SaveFile(timeout=30)

# If your model requires loading a file object, you use the task pre-packaged
# with LUME-services:
# load_file_task = LoadFile(timeout=30)

# If your model requires loading a results database entry, you can use the LoadDBResult
# task packaged with LUME-services:
# load_db_result_task = LoadDBResult(timeout=10)


def lcls_cu_inj_nn_model_flow():
    logger = get_run_logger()
    logger.info(f'Starting flow run...')
    # CONFIGURE LUME-SERVICES
    # see https://slaclab.github.io/lume-services/workflows/#configuring-flows-for-use-with-lume-services
    #configure = configure_lume_services()

    # CHECK WHETHER THE FLOW IS RUNNING LOCALLY
    # If the flow runs using a local backend, the results service will not be available
    #running_local = check_local_execution()
    #running_local.set_upstream(configure)

    # SET UP INPUT VARIABLE PARAMETERS.
    # These are parameters that can be supplied to the workflow at runtime
    input_variable_parameter_dict = {}
    for var in INPUT_VARIABLES:
        input_variable_parameter_dict[var.name] = load_input(var.name, var)


    # If your model requires loading a file object, you can use the LoadFile task
    # pre-packaged with LUME-services. The load_file_task is defined in a comment above
    # outside of this flow scope. The task parameters can be conveniently accessed for
    # adding to flow parameters:
    # file_parameters = load_file_task.parameters
    # loaded_obj = load_file_task(**file_parameters)

    # If your model requires loading a result object stored in the database, you can
    # use the LoadDBResult task pre-packaged with LUME-services The load_db_result_task
    # is defined in a comment above outside of this flow scope. The task parameters can
    # be conveniently accessed for adding to flow parameters:
    # result_parameters = load_db_result_task.parameters
    # db_result = load_db_result(flow_id=flow_id_of_result_flow, attribute="outputs")
    # To access a sepecific value returned in the db_result, in this case the value of
    # the output variable named "output1":
    # db_result = load_db_result(
    #                   flow_id=flow_id_of_result_flow,
    #                   attribute="outputs",
    #                   attribute_index=["output1"]
    # )

    # ORGANIZE INPUT VARIABLE VALUES LUME-MODEL VARIABLES
    formatted_input_variables = prepare_lume_model_variables(
        input_variable_parameter_dict, INPUT_VARIABLES
    )

    # If additional preprocessing is necessary, the user can implement a preprocessing task
    # formatted_input_vars = preprocessing_task(formatted_input_vars)

    # RUN EVALUATION
    output_variables = evaluate(formatted_input_variables)
    # If we had settings we were passing to the model, it would look like:
    # results = evaluate(formatted_input_vars, settings={
    #    "setting_1": setting_1,
    #    "setting_2": setting_2
    # })

    # SAVE A FILE WITH SOME FORMATTED DATA
    # This assumes the output is a text file, but see https://slaclab.github.io/lume-services/api/files/files/ # noqa
    # for custom types. If the formats supported do not suit your needs, you can
    # alternatively subclass File for custom serialization.
    #file_data = format_file(output_variables)


    # MARK CONFIGURATION OF LUME_SERVICES AS AN UPSTREAM TASK
    # tasks using backend services like filesystem and results db must mark configure
    # as an upstream task

    # add "filename" and "filesystem_identifier to the flow parameters"
    #file_parameters = save_file_task.parameters
    #saved_file_rep = save_file_task(file_data, file_type=TextFile, **file_parameters)


    # MARK CONFIGURATION OF LUME_SERVICES AS AN UPSTREAM TASK
    # tasks using backend services like filesystem and results db must mark configure
    # as an upstream task
    #saved_file_rep.set_upstream(configure)


    # SAVE RESULTS TO RESULTS DATABASE, requires LUME-services results backend, still work in progress
    #if not running_local:
    #    # CREATE LUME-services Result object
    #    formatted_result = format_result(
    #        input_variables=formatted_input_variables, output_variables=output_variables
    #    )

        # RUN DATABASE_SAVE_TASK
    #    saved_model_rep = save_db_result_task(formatted_result)
    #    saved_model_rep.set_upstream(configure)


def get_flow():
    return flow
