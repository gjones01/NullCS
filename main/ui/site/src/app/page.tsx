import { CinematicExperience } from "@/components/cinematic/experience";
import sample from "../../public/assets/observatory/encounter-sample.json";

export default function HomePage() {
  return (
    <>
      <noscript>
        <style>
          {
            ".pipeline-sequence{height:auto}.pipeline-sticky{position:relative;top:0}"
          }
        </style>
      </noscript>
      <CinematicExperience channels={sample.channels} />
    </>
  );
}
