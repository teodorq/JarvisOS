targetScope = 'subscription'

@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Deployment region. Poland Central keeps the service close to the desktop client.')
param location string = 'polandcentral'

@description('Public container image containing the JARVIS OS cloud planner.')
param containerImage string

@secure()
@description('Bearer token shared only by the desktop client and Container App.')
param apiToken string

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${namePrefix}-cloud'
  location: location
  tags: {
    application: 'JARVIS OS'
    costProfile: '20-pln-guarded'
  }
}

module cloudPlanner './main.bicep' = {
  name: '${namePrefix}-cloud-planner'
  scope: resourceGroup
  params: {
    namePrefix: namePrefix
    location: location
    containerImage: containerImage
    apiToken: apiToken
  }
}

output resourceGroupName string = resourceGroup.name
output endpoint string = cloudPlanner.outputs.endpoint
output healthUrl string = cloudPlanner.outputs.healthUrl
