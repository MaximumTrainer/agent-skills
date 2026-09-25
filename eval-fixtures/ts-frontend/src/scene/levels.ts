import * as THREE from 'three';

export function unloadLevel(scene: THREE.Scene, group: THREE.Group) {
  scene.remove(group);
}
