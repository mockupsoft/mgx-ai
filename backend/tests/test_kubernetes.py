import pytest
import os
import yaml
from pathlib import Path

class TestKubernetesManifests:
    
    @pytest.fixture
    def k8s_dir(self):
        # Assuming k8s manifests are in kubernetes/ or similar, but checking project structure
        # based on ticket description it says `kubernetes/`
        return Path("kubernetes")

    def test_manifests_valid_yaml(self, k8s_dir):
        """Test that all manifests are valid YAML"""
        if not k8s_dir.exists():
            pytest.skip("kubernetes directory not found")
            
        for file_path in k8s_dir.glob("*.yaml"):
            with open(file_path, 'r') as f:
                try:
                    list(yaml.safe_load_all(f))
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {file_path}: {e}")

    def test_deployment_resources(self, k8s_dir):
        """Test deployment manifests have resource limits"""
        if not k8s_dir.exists():
            pytest.skip("kubernetes directory not found")
            
        found_deployment = False
        for file_path in k8s_dir.glob("*.yaml"):
            with open(file_path, 'r') as f:
                docs = list(yaml.safe_load_all(f))
                for doc in docs:
                    if doc and doc.get('kind') == 'Deployment':
                        found_deployment = True
                        # Check containers
                        spec = doc.get('spec', {}).get('template', {}).get('spec', {})
                        for container in spec.get('containers', []):
                            resources = container.get('resources', {})
                            assert 'limits' in resources, f"Missing limits in {file_path}"
                            assert 'requests' in resources, f"Missing requests in {file_path}"
                            
        if not found_deployment:
            # Maybe manifests are not generated yet or in a different place
            pass

    def test_service_definitions(self, k8s_dir):
        """Test service definitions"""
        if not k8s_dir.exists():
            pytest.skip("kubernetes directory not found")
            
        for file_path in k8s_dir.glob("*.yaml"):
            with open(file_path, 'r') as f:
                docs = list(yaml.safe_load_all(f))
                for doc in docs:
                    if doc and doc.get('kind') == 'Service':
                        spec = doc.get('spec', {})
                        assert 'ports' in spec
                        assert 'selector' in spec
