#!/bin/bash
set -e

echo "ECS_CLUSTER=${cluster_name}" >> /etc/ecs/ecs.config
echo "ECS_ENABLE_CONTAINER_METADATA=true" >> /etc/ecs/ecs.config

# Wait for EBS volume to attach
while [ ! -e ${device_name} ]; do
  echo "Waiting for EBS volume..."
  sleep 5
done

# Format if not already formatted
if ! blkid ${device_name}; then
  mkfs -t ext4 ${device_name}
fi

# Mount volume
mkdir -p /mnt/qdrant-data
mount ${device_name} /mnt/qdrant-data
echo "${device_name} /mnt/qdrant-data ext4 defaults,nofail 0 2" >> /etc/fstab

# Set permissions for Qdrant container
chown 1000:1000 /mnt/qdrant-data
