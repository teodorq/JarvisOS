targetScope = 'subscription'

@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Deployment region. Poland Central keeps the service close to the desktop client.')
param location string = 'polandcentral'

@description('Public container image containing the JARVIS OS cloud planner.')
param containerImage string

@description('Exact Git commit represented by the deployed container image.')
param buildSha string = 'development'

@description('Allow only empty inactive V3 SHADOW initialization after complete verified PAPER evidence.')
param v3ShadowAutoInitializeEnabled bool = false

@secure()
@description('Bearer token shared only by the desktop client and Container App.')
param apiToken string

@secure()
@description('Read-only Twelve Data key used by the Azure PAPER job.')
param twelveDataApiKey string

@secure()
@description('Read-only FMP key used only for an independent price cross-check.')
param fmpApiKey string

@description('Microsoft Entra application client ID used by the phone page.')
param phoneEntraClientId string

@secure()
@description('Microsoft Entra application secret used by Container Apps authentication.')
param phoneEntraClientSecret string

@description('Microsoft Entra object ID of the only account allowed to use the phone page.')
param phoneOwnerPrincipalId string

@secure()
@description('Private recipient for the 4.60 EUR Azure budget alerts.')
param budgetAlertEmail string

module costGuardrail './budget.bicep' = {
  name: '${namePrefix}-cost-guardrail'
  params: {
    budgetName: namePrefix
    budgetAlertEmail: budgetAlertEmail
  }
}

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
    v3ShadowAutoInitializeEnabled: v3ShadowAutoInitializeEnabled
    apiToken: apiToken
    twelveDataApiKey: twelveDataApiKey
    fmpApiKey: fmpApiKey
    phoneEntraClientId: phoneEntraClientId
    phoneEntraClientSecret: phoneEntraClientSecret
    phoneOwnerPrincipalId: phoneOwnerPrincipalId
  }
}

output resourceGroupName string = resourceGroup.name
output endpoint string = cloudPlanner.outputs.endpoint
output healthUrl string = cloudPlanner.outputs.healthUrl
output phoneUrl string = cloudPlanner.outputs.phoneUrl
output tradingUrl string = cloudPlanner.outputs.tradingUrl
output remoteStorageAccountName string = cloudPlanner.outputs.remoteStorageAccountName
output paperJobName string = cloudPlanner.outputs.paperJobName
output paperStateContainerName string = cloudPlanner.outputs.paperStateContainerName
output paperStatusContainerName string = cloudPlanner.outputs.paperStatusContainerName
output budgetResourceId string = costGuardrail.outputs.budgetResourceId
