targetScope = 'subscription'

@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Deployment region. Poland Central keeps the service close to the desktop client.')
param location string = 'polandcentral'

@description('Public container image containing the JARVIS OS cloud planner.')
param containerImage string

@description('Exact Git commit represented by the deployed container image.')
param buildSha string = 'development'

@secure()
@description('Bearer token shared only by the desktop client and Container App.')
param apiToken string

@description('Microsoft Entra application client ID used by the phone page.')
param phoneEntraClientId string

@secure()
@description('Microsoft Entra application secret used by Container Apps authentication.')
param phoneEntraClientSecret string

@description('Microsoft Entra object ID of the only account allowed to use the phone page.')
param phoneOwnerPrincipalId string

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${namePrefix}-cloud'
  location: location
  tags: {
    application: 'JARVIS OS'
    costProfile: '4-60-eur-budget-alert'
  }
}

module cloudPlanner './main.bicep' = {
  name: '${namePrefix}-cloud-planner'
  scope: resourceGroup
  params: {
    namePrefix: namePrefix
    location: location
    containerImage: containerImage
    buildSha: buildSha
    apiToken: apiToken
    phoneEntraClientId: phoneEntraClientId
    phoneEntraClientSecret: phoneEntraClientSecret
    phoneOwnerPrincipalId: phoneOwnerPrincipalId
  }
}

output resourceGroupName string = resourceGroup.name
output endpoint string = cloudPlanner.outputs.endpoint
output healthUrl string = cloudPlanner.outputs.healthUrl
output phoneUrl string = cloudPlanner.outputs.phoneUrl
output remoteStorageAccountName string = cloudPlanner.outputs.remoteStorageAccountName
