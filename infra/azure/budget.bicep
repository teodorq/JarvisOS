targetScope = 'subscription'

@description('Azure Cost Management budget name.')
param budgetName string = 'jarvis-os'

@description('Monthly budget amount in the subscription billing currency.')
param budgetAmount string = '4.60'

@secure()
@description('Private recipient for Azure Cost Management alerts.')
param budgetAlertEmail string

@description('First day of the first tracked billing month.')
param budgetStartDate string = '2026-08-01T00:00:00Z'

@description('Last day covered by the current budget guardrail.')
param budgetEndDate string = '2028-07-31T00:00:00Z'

var alertRecipients = [
  budgetAlertEmail
]

resource monthlyBudget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: budgetName
  properties: {
    amount: json(budgetAmount)
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
      endDate: budgetEndDate
    }
    notifications: {
      actual_GreaterThan_50_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        thresholdType: 'Actual'
        locale: 'pl-pl'
        contactEmails: alertRecipients
        contactGroups: []
        contactRoles: []
      }
      actual_GreaterThan_80_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
        locale: 'pl-pl'
        contactEmails: alertRecipients
        contactGroups: []
        contactRoles: []
      }
      actual_GreaterThan_100_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Actual'
        locale: 'pl-pl'
        contactEmails: alertRecipients
        contactGroups: []
        contactRoles: []
      }
    }
  }
}

output budgetResourceId string = monthlyBudget.id
output monthlyAmount string = budgetAmount
