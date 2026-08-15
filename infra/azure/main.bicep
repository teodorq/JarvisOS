@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Azure region for the Container Apps environment.')
param location string = resourceGroup().location

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

var tags = {
  application: 'JARVIS OS'
  component: 'cloud-planner'
  costProfile: '4-60-eur-budget-alert'
}

var remoteStorageName = take('jaros${uniqueString(resourceGroup().id)}relay', 24)

resource remoteStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: remoteStorageName
  location: location
  tags: union(tags, {
    component: 'phone-command-relay'
  })
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: remoteStorage
  name: 'default'
}

resource commandsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'commands'
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: remoteStorage
  name: 'default'
}

resource commandsQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueService
  name: 'commands'
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
  identity: {
    type: 'SystemAssigned'
  }
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
        {
          name: 'phone-entra-client-secret'
          value: phoneEntraClientSecret
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
              name: 'JARVIS_OS_BUILD_SHA'
              value: buildSha
            }
            {
              name: 'JARVIS_OS_CLOUD_API_TOKEN'
              secretRef: 'api-token'
            }
            {
              name: 'JARVIS_OS_PHONE_PRINCIPAL_ID'
              value: phoneOwnerPrincipalId
            }
            {
              name: 'JARVIS_OS_REMOTE_STORAGE_ACCOUNT'
              value: remoteStorage.name
            }
            {
              name: 'JARVIS_OS_REMOTE_TABLE'
              value: commandsTable.name
            }
            {
              name: 'JARVIS_OS_REMOTE_QUEUE'
              value: commandsQueue.name
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

var storageTableDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
)
var storageQueueDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
)
var storageQueueMessageProcessorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8a0f0c08-91a1-4084-bc3d-661d67233fed'
)

resource plannerTableAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(commandsTable.id, plannerApp.id, storageTableDataContributorRoleId)
  scope: commandsTable
  properties: {
    principalId: plannerApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageTableDataContributorRoleId
  }
}

resource plannerQueueAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(commandsQueue.id, plannerApp.id, storageQueueDataContributorRoleId)
  scope: commandsQueue
  properties: {
    principalId: plannerApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageQueueDataContributorRoleId
  }
}

resource ownerQueueAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(commandsQueue.id, phoneOwnerPrincipalId, storageQueueMessageProcessorRoleId)
  scope: commandsQueue
  properties: {
    principalId: phoneOwnerPrincipalId
    principalType: 'User'
    roleDefinitionId: storageQueueMessageProcessorRoleId
  }
}

resource phoneAuth 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: plannerApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'AllowAnonymous'
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        isAutoProvisioned: false
        login: {
          loginParameters: [
            'response_type=code'
            'response_mode=query'
            'scope=openid profile email'
          ]
        }
        registration: {
          clientId: phoneEntraClientId
          clientSecretSettingName: 'phone-entra-client-secret'
          openIdIssuer: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            phoneEntraClientId
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              identities: [
                phoneOwnerPrincipalId
              ]
            }
          }
        }
      }
    }
    login: {
      cookieExpiration: {
        convention: 'FixedTime'
        timeToExpiration: '01:00:00'
      }
      preserveUrlFragmentsForLogins: false
      tokenStore: {
        enabled: false
      }
    }
  }
}
output endpoint string = 'https://${plannerApp.properties.configuration.ingress.fqdn}'
output healthUrl string = 'https://${plannerApp.properties.configuration.ingress.fqdn}/health'
output phoneUrl string = 'https://${plannerApp.properties.configuration.ingress.fqdn}/phone'
output remoteStorageAccountName string = remoteStorage.name
output remoteQueueName string = commandsQueue.name
