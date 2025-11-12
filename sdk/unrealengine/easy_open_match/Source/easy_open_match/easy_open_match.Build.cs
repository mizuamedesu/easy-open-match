// Some copyright should be here...

using System.IO;
using UnrealBuildTool;

public class easy_open_match : ModuleRules
{
	private string ThirdPartyPath
	{
		get { return Path.GetFullPath(Path.Combine(ModuleDirectory, "../../ThirdParty/")); }
	}

	public easy_open_match(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = true;
		bUseRTTI = true;
		bEnableUndefinedIdentifierWarnings = false;

		// Disable specific warnings that are treated as errors
		if (Target.Platform == UnrealTargetPlatform.Win64)
		{
			// Disable C4800 (implicit conversion to bool) and C4668 (undefined macro)
			PrivateDefinitions.Add("_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS");
		}
		else
		{
			// For Clang (Android, iOS, etc): define NDK macro to avoid undef warnings
			PublicDefinitions.Add("__NDK_MAJOR__=21");
			PublicDefinitions.Add("__NDK_MAJOR=21");
		}

		// gRPC definitions
		PublicDefinitions.Add("GOOGLE_PROTOBUF_NO_RTTI");
		PublicDefinitions.Add("GPR_FORBID_UNREACHABLE_CODE");
		PublicDefinitions.Add("GRPC_ALLOW_EXCEPTIONS=0");
		PublicDefinitions.Add("GOOGLE_PROTOBUF_INTERNAL_DONATE_STEAL_INLINE=0");

		PublicIncludePaths.AddRange(
			new string[] {
				Path.Combine(ThirdPartyPath, "Includes"),
			}
		);

		PrivateIncludePaths.AddRange(
			new string[] {
				// ... add other private include paths required here ...
			}
		);

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				// ... add other public dependencies that you statically link with here ...
			}
		);

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"CoreUObject",
				"Engine",
				"Slate",
				"SlateCore",
				// ... add private dependencies that you statically link with here ...
			}
		);

		// Add gRPC libraries
		string LibrariesPath = Path.Combine(ThirdPartyPath, "Libraries");

		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "address_sorting.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "cares.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "gpr.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "grpc_unsecure.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "grpc++_unsecure.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "libprotobuf.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "upb.lib"));

		// Abseil libraries
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_base.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_malloc_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_raw_logging_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_spinlock_wait.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_throw_delegate.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_time.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_time_zone.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_civil_time.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_graphcycles_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_synchronization.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_cord.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_str_format_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_strings.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_strings_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_status.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_statusor.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_bad_optional_access.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_bad_variant_access.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_stacktrace.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_symbolize.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_int128.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_debugging_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_demangle_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_hashtablez_sampler.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_raw_hash_set.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_hash.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_city.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_low_level_hash.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_exponential_biased.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_cord_internal.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_cordz_handle.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_cordz_info.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_cordz_functions.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_distributions.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_seed_sequences.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_pool_urbg.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_randen.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_randen_hwaes.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_randen_hwaes_impl.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_randen_slow.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_platform.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_internal_seed_material.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_random_seed_gen_exception.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_log_severity.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "absl_strerror.lib"));

		// BoringSSL libraries
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "ssl.lib"));
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "crypto.lib"));

		// re2 library
		PublicAdditionalLibraries.Add(Path.Combine(LibrariesPath, "re2.lib"));

		// Windows system libraries
		if (Target.Platform == UnrealTargetPlatform.Win64)
		{
			PublicSystemLibraries.Add("ws2_32.lib");
			PublicSystemLibraries.Add("advapi32.lib");
			PublicSystemLibraries.Add("dbghelp.lib");
		}

		// Use UE's zlib
		AddEngineThirdPartyPrivateStaticDependencies(Target, "zlib");

		DynamicallyLoadedModuleNames.AddRange(
			new string[]
			{
			}
		);
	}
}
