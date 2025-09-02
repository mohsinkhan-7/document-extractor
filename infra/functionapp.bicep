targetScope = 'resourceGroup'

@description('Azure location')
param location string

@description('Environment name (e.g., dev, prod)')
param environmentName string


var token = uniqueString(subscription().id, resourceGroup().id, location, environmentName)

var saName = 'azsa${token}'
var planName = 'az-afp-${token}'
var funcName = 'az-func-${token}'
var acrName = 'azacr${token}'
var uamiName = 'az-id-${token}'
var aiName = 'az-ai-${token}'

// Storage Account
resource sa 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: saName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

// Application Insights
resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: aiName
  location: location
  kind: 'web'
  properties: { Application_Type: 'web' }
}

// App Service Plan (EP1 Linux)
resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: planName
  location: location
  sku: {
    name: 'EP1'
    tier: 'ElasticPremium'
  }
  properties: {
    reserved: true
  }
}

// ACR
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// User-assigned identity
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
}

// AcrPull role assignment
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uami.id, 'AcrPull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Function App (Linux) using container image
resource func 'Microsoft.Web/sites@2022-09-01' = {
  name: funcName
  location: location
  kind: 'functionapp,linux,container'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${sa.name};AccountKey=${listKeys(resourceId('Microsoft.Storage/storageAccounts', sa.name), '2023-05-01').keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: ''
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${acr.properties.loginServer}'
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'true'
        }
      ]
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: uami.id
      alwaysOn: true
    }
    httpsOnly: true
  }
}

output FUNCTION_APP_NAME string = func.name
output ACR_LOGIN_SERVER string = acr.properties.loginServer
