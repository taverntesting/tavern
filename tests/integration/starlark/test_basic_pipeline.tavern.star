# Basic Starlark pipeline test
# This test demonstrates loading stages via include() and running them with run_stage()

# Load the stages from a YAML file using include()
config_file = include("stages.yaml")
stages = config_file["stages"]

# Create a dictionary of stages by id
stages_by_id = {}
for stage in stages:
    stage_id = stage.get("id")
    if stage_id:
        stages_by_id[stage_id] = stage

def run_pipeline(ctx):
    """Main pipeline function that runs the test stages.

    Args:
        ctx: Variables dict (updated with values from previous stages)

    Returns:
        Optional return value indicating test result
    """

    # First get a cookie - run_stage returns (variables, response)
    variables, resp = run_stage(stages_by_id["get-cookie"])

    # Check if the stage succeeded
    if resp.failure:
        fail("Get cookie stage failed")

    # Echo a value back using updated variables
    variables, resp = run_stage(stages_by_id["echo-value"])

    # Check if the stage succeeded
    if resp.failure:
        fail("Echo stage failed")

    # All done - test passed
    return "OK"
