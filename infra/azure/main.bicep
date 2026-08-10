@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Azure region for the Container Apps environment.')
param location string = resourceGroup().location

@description('Public container image containing the JARVIS OS cloud planner.')
param containerImage string

@secure()
@description('Bearer token shared only by the desktop client and Container App.')
param apiToken string

var tags = {
  application: 'JARVIS OS'
  component: 'cloud-planner'
  costProfile: '4-60-eur-budget-alert'
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
              name: 'JARVIS_OS_CLOUD_ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'JARVIS_OS_CLOUD_API_TOKEN'
              secretRef: 'api-token'
            }
            {
              name: 'JARVIS_OS_CLOUD_REQUESTS_PER_MINUTE'
              value: '30'
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
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 1
              periodSeconds: 2
              timeoutSeconds: 1
              failureThreshold: 10
              successThreshold: 1
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 1
              periodSeconds: 10
              timeoutSeconds: 2
              failureThreshold: 3
              successThreshold: 1
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 30
              timeoutSeconds: 2
              failureThreshold: 3
              successThreshold: 1
            }
          ]
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
