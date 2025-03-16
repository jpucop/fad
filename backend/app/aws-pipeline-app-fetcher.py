import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
codepipeline = boto3.client('codepipeline')
codedeploy = boto3.client('codedeploy')
ecs = boto3.client('ecs')
elbv2 = boto3.client('elbv2')
logs = boto3.client('logs')

def get_all_pipelines():
    """List all CodePipeline pipelines in the account."""
    try:
        response = codepipeline.list_pipelines()
        pipelines = response['pipelines']
        while 'nextToken' in response:
            response = codepipeline.list_pipelines(nextToken=response['nextToken'])
            pipelines.extend(response['pipelines'])
        return [p['name'] for p in pipelines]
    except ClientError as e:
        print(f"Error listing pipelines: {e}")
        return []

def get_codedeploy_info_from_pipeline(pipeline_name):
    """Extract CodeDeploy application and deployment group from pipeline."""
    try:
        response = codepipeline.get_pipeline(name=pipeline_name)
        pipeline = response['pipeline']

        for stage in pipeline['stages']:
            for action in stage['actions']:
                if action['actionTypeId']['provider'] == 'CodeDeployToECS':
                    config = action.get('configuration', {})
                    return {
                        'app_name': config.get('ApplicationName'),
                        'deployment_group': config.get('DeploymentGroupName')
                    }
        return None
    except ClientError as e:
        print(f"Error getting pipeline {pipeline_name}: {e}")
        return None

def get_target_group_arns(target_group_names):
    """Resolve target group names to ARNs."""
    try:
        response = elbv2.describe_target_groups(Names=target_group_names)
        return [tg['TargetGroupArn'] for tg in response['TargetGroups']]
    except ClientError as e:
        print(f"Error getting Target Group ARNs: {e}")
        return []

def get_ecs_and_alb_from_deployment_group(app_name, deployment_group):
    """Get ECS cluster, service, and ALB info from CodeDeploy deployment group."""
    try:
        response = codedeploy.get_deployment_group(
            applicationName=app_name,
            deploymentGroupName=deployment_group
        )
        ecs_config = response['deploymentGroupInfo'].get('ecsServices', [{}])[0]
        lb_config = response['deploymentGroupInfo'].get('loadBalancerInfo', {}).get('targetGroupPairInfoList', [{}])[0]
        
        print(f"DEBUG: lb_config = {lb_config}")

        target_group_names = [tg.get('name') for tg in lb_config.get('targetGroups', []) if tg.get('name')]
        target_group_arns = get_target_group_arns(target_group_names)

        if not target_group_arns:
            print(f"WARNING: No Target Group ARNs found for deployment group {deployment_group}")

        return {
            'cluster': ecs_config.get('clusterName'),
            'service': ecs_config.get('serviceName'),
            'alb_arn': lb_config.get('loadBalancerInfo', {}).get('name'),
            'target_group_arns': target_group_arns
        }
    except ClientError as e:
        print(f"Error getting deployment group {deployment_group}: {e}")
        return None

def get_alb_details(target_group_arn):
    """Get ALB DNS name, protocol, port, and TLS cert."""
    try:
        response = elbv2.describe_target_groups(TargetGroupArns=[target_group_arn])
        target_group = response['TargetGroups'][0]
        lb_arns = target_group.get('LoadBalancerArns', [])

        if not lb_arns:
            print(f"WARNING: No Load Balancer associated with Target Group {target_group_arn}")
            return None
        
        lb_arn = lb_arns[0]
        lb_response = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])
        lb = lb_response['LoadBalancers'][0]
        
        listener_response = elbv2.describe_listeners(LoadBalancerArn=lb_arn)
        listener = next((l for l in listener_response['Listeners'] if l['Port'] in [443, 80]), None)
        
        cert_arn = None
        protocol = 'HTTP'
        port = 80
        if listener:
            port = listener['Port']
            protocol = listener['Protocol']
            certs = listener.get('Certificates', [])
            if certs:
                cert_arn = certs[0]['CertificateArn']
        
        print(f"DEBUG: ALB details fetched: {lb}")

        return {
            'alb_arn': lb_arn,
            'dns_name': lb['DNSName'],
            'protocol': protocol,
            'port': port,
            'cert_arn': cert_arn
        }
    except ClientError as e:
        print(f"Error getting ALB details: {e}")
        return None

def get_deployment_info(pipeline_name):
    """Gather all deployment info from a pipeline with CodeDeploy to ECS."""
    codedeploy_info = get_codedeploy_info_from_pipeline(pipeline_name)
    print(f"codedeploy_info: {codedeploy_info}")
    
    if not codedeploy_info:
        return None

    deployment_info = get_ecs_and_alb_from_deployment_group(
        codedeploy_info['app_name'],
        codedeploy_info['deployment_group']
    )
    if not deployment_info:
        return None

    alb_details = get_alb_details(deployment_info['target_group_arns'][0]) if deployment_info['target_group_arns'] else None
    
    app_url = f"{alb_details['protocol'].lower()}://{alb_details['dns_name']}:{alb_details['port']}" if alb_details else "N/A"

    return {
        'pipeline_name': pipeline_name,
        'cluster_name': deployment_info['cluster'],
        'service_name': deployment_info['service'],
        'alb_info': alb_details,
        'cloudwatch_log_groups': deployment_info.get('log_groups', []),
        'app_url': app_url
    }

if __name__ == "__main__":
    pipelines = get_all_pipelines()
    print(f"Found {len(pipelines)} pipelines: {pipelines}")

    for pipeline_name in pipelines:
        info = get_deployment_info(pipeline_name)
        print(f"info: {info}")
