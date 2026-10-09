@description('Short lowercase prefix used for Azure resource names.')
param namePrefix string = 'jarvis-os'

@description('Azure region for the existing Container Apps environment.')
param location string = resourceGroup().location

@description('Immutable public container image containing JARVIS OS.')
param containerImage string

@description('Exact Git commit represented by the deployed container image.')
param buildSha string

@description('Existing Storage account used for private PAPER state.')
param storageAccountName string

@description('Existing Container Apps environment name.')
param managedEnvironmentName string = '${namePrefix}-env'

@secure()
@description('Read-only Twelve Data key used by the Azure PAPER job.')
param twelveDataApiKey string

@secure()
@description('Read-only FMP key used only for an independent price cross-check.')
param fmpApiKey string

var tags = {
  application: 'JARVIS OS'
  component: 'forex-paper-scheduler'
  costProfile: '4-60-eur-budget-alert'
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storage
  name: 'default'
}

resource paperStateContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'forex-paper'
  properties: {
    publicAccess: 'None'
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: managedEnvironmentName
}

resource paperJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${namePrefix}-forex-paper'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 600
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '2,17,32,47 * * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
      secrets: [
        {
          name: 'twelve-data-api-key'
          value: twelveDataApiKey
        }
        {
          name: 'fmp-api-key'
          value: fmpApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'forex-paper'
          image: containerImage
          command: [
            'python'
          ]
          args: [
            '-m'
            'cloud_service.forex_paper_job'
          ]
          env: [
            {
              name: 'JARVIS_OS_BUILD_SHA'
              value: buildSha
            }
            {
              name: 'JARVIS_OS_FOREX_CLOUD_ENABLED'
              value: 'true'
            }
            {
              name: 'JARVIS_OS_FOREX_DATA_ENABLED'
              value: 'true'
            }
            {
              name: 'JARVIS_OS_FOREX_PAPER_AUTOPILOT_ENABLED'
              value: 'true'
            }
            {
              name: 'JARVIS_OS_FOREX_PRIMARY_PROVIDER'
              value: 'TWELVE_DATA_CLOUD'
            }
            {
              name: 'JARVIS_OS_TWELVE_DATA_API_KEY'
              secretRef: 'twelve-data-api-key'
            }
            {
              name: 'JARVIS_OS_FMP_API_KEY'
              secretRef: 'fmp-api-key'
            }
            {
              name: 'JARVIS_OS_REMOTE_STORAGE_ACCOUNT'
              value: storage.name
            }
            {
              name: 'JARVIS_OS_FOREX_CLOUD_CONTAINER'
              value: paperStateContainer.name
            }
            {
              name: 'JARVIS_OS_FOREX_CLOUD_STATE_BLOB'
              value: 'state/paper-state.zip'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

resource paperJobStateAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(paperStateContainer.id, paperJob.id, storageBlobDataContributorRoleId)
  scope: paperStateContainer
  properties: {
    principalId: paperJob.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

output paperJobName string = paperJob.name
output paperStateContainerName string = paperStateContainer.name
