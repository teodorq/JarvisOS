@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Azure region for the Container Apps environment.')
param location string = resourceGroup().location

@description('Public container image containing the JARVIS cloud planner.')
param containerImage string

@secure()
@description('Bearer token shared only by the desktop client and Container App.')
param apiToken string

var tags = {
  application: 'JARVIS OS'
  component: 'cloud-planner'
  costProfile: '20-pln-guarded'
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  tags: tags
  properties: {}
}

resource plannerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-planner'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      secrets: [
        {
          name: 'api-token'
          value: apiToken
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'planner'
          image: containerImage
          env: [
            {
              name: 'JARVIS_ENV'
              value: 'production'
            }
            {
              name: 'JARVIS_CLOUD_API_TOKEN'
              secretRef: 'api-token'
            }
            {
              name: 'PORT'
              value: '8000'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output endpoint string = 'https://${plannerApp.properties.configuration.ingress.fqdn}'
output healthUrl string = 'https://${plannerApp.properties.configuration.ingress.fqdn}/health'
