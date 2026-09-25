import { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import { useStore } from '../state/store';

export function Boat({ url }: { url: string }) {
  const ref = useRef<any>(null);
  const [angle, setAngle] = useState(0);
  const state = useStore();
  const { scene } = useGLTF(url);

  useFrame((_, delta) => {
    setAngle((a) => a + delta * state.strokeRate * 0.1);
    if (ref.current) ref.current.rotation.y = angle;
  });

  return <primitive ref={ref} object={scene} position={[0, 0, 0]} />;
}
