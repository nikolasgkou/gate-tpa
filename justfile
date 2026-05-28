resource-group := "gate-tpa-mvp"
location := "westeurope"
deployment := "gate-tpa-pbx"
ssh-key := ".private_notes/gate-tpa-azure.pub"

azure-key:
    mkdir -p .private_notes
    test -f {{ssh-key}} || ssh-keygen -t ed25519 -f .private_notes/gate-tpa-azure -N "" -C "gate-tpa-azure"

azure-pbx-preview: azure-key
    az group create --name {{resource-group}} --location {{location}}
    az deployment group what-if --resource-group {{resource-group}} --name {{deployment}} --template-file infra/main.bicep --parameters adminSshPublicKey="$(cat {{ssh-key}})"

azure-pbx-deploy: azure-key
    az group create --name {{resource-group}} --location {{location}}
    az deployment group create --resource-group {{resource-group}} --name {{deployment}} --template-file infra/main.bicep --parameters adminSshPublicKey="$(cat {{ssh-key}})"

azure-pbx-credentials:
    az vm run-command invoke --resource-group {{resource-group}} --name gate-tpa-pbx --command-id RunShellScript --scripts 'cat /root/gate-tpa-linphone-1001.txt' --query "value[0].message" --output tsv
