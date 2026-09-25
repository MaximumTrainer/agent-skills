import { Canvas } from '@react-three/fiber';
import { Boat } from './Boat';
import { useStore } from '../state/store';

export function Viewer() {
  const state = useStore();
  return (
    <Canvas dpr={window.devicePixelRatio} camera={{ position: [0, 5, 10] }}>
      <ambientLight intensity={0.8} />
      {state.showCoxView && <Boat url="/models/eight.glb" />}
      {Array.from({ length: 2000 }).map((_, i) => (
        <mesh key={i} position={[i % 50, 0, Math.floor(i / 50)]}>
          <boxGeometry args={[0.2, 0.2, 0.2]} />
          <meshStandardMaterial color="#4488cc" />
        </mesh>
      ))}
    </Canvas>
  );
}
