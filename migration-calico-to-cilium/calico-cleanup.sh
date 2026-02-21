#!/bin/sh
set +x
if [ "$1" = "pod" ]; then
  if [ -z ${NODE+x} ]; then
    echo "\$NODE variable isn't set"
    exit 1
  fi
  cat <<EOF | kubectl apply -f -
$(cat calico-cleanup-pod.yml | sed "s/__CHANGEME__/$NODE/g")
EOF
  sleep 15
  kubectl exec cilium-killed-calico -n kube-system -- /bin/sh -c "`cat calico-cleanup.sh`"
  kubectl delete pod cilium-killed-calico -n kube-system
else
  echo "Flushing all the calico iptables chains in the nat table..."
  iptables-save -t nat | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t nat -F $line; done
  echo "Flushing all the calico iptables chains in the raw table..."
  iptables-save -t raw | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t raw -F $line; done
  echo "Flushing all the calico iptables chains in the mangle table..."
  iptables-save -t mangle | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t mangle -F $line; done
  echo "Flushing all the calico iptables chains in the filter table..."
  iptables-save -t filter | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t filter -F $line; done
  echo "Cleaning up calico rules from the nat table..."
  iptables-save -t nat | grep -e '--comment "cali:' | cut -c 3- | sed 's/^ *//;s/ *$//' | xargs -l1 iptables -t nat -D
  echo "Cleaning up calico rules from the raw table..."
  iptables-save -t raw | grep -e '--comment "cali:' | cut -c 3- | sed 's/^ *//;s/ *$//' | xargs -l1 iptables -t raw -D
  echo "Cleaning up calico rules from the mangle table..."
  iptables-save -t mangle | grep -e '--comment "cali:' | cut -c 3- | sed 's/^ *//;s/ *$//' | xargs -l1 iptables -t mangle -D
  echo "Cleaning up calico rules from the filter table..."
  iptables-save -t filter | grep -e '--comment "cali:' | cut -c 3- | sed 's/^ *//;s/ *$//' | xargs -l1 iptables -t filter -D
  ip route flush proto bird
fi